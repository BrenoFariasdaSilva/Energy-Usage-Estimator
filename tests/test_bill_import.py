"""Copel DANF3E regression tests. No private bills are included in the repository."""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfWriter

from energy_estimator.bill_import import (
    BillImportError,
    UnsupportedBillError,
    UnreadableBillError,
    extract_copel_bill_text,
    parse_copel_pdf,
)
from energy_estimator.models import Tariff
from energy_estimator.storage import JsonStore

HEADER = """DANF3E - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRONICA DE ENERGIA ELETRICA
Copel Distribuição S.A.
CNPJ 04.368.898/0001-06
11/2026 25/12/2026 R$192,72
"""
ENERGY = "ENERGIA ELET CONSUMO kWh 168 0,415476 69,80 4,32 13,26 0,310850 ICMS 172,45 19% 32,76\n"
DISTRIBUTION = "ENERGIA ELET USO SISTEMA kWh 168 0,611012 102,65 6,35 19,50 0,457170\n"
LIGHT = "CONT ILUMIN PUBLICA MUNICIPIO UN 20,270000 20,27\n"
METER = "0045158902 CONSUMO kWh TP 2156 2324 1 168\n"
TOTAL = "TOTAL 192,72 10,67 32,76\n"
HISTORY = "HISTÓRICO DE CONSUMO / kWh\nCONSUMO FATURADO\nNOV26 168 31\nOUT26 215 32\n"
BILL = HEADER + ENERGY + DISTRIBUTION + LIGHT + HISTORY + METER + TOTAL


def test_actual_reference_layout_extraction() -> None:
    parsed = extract_copel_bill_text(BILL)
    assert parsed.reference == "11/2026"
    assert parsed.total_brl == Decimal("192.72")
    assert parsed.billed_kwh == Decimal("168")
    assert parsed.energy_unit_price == Decimal("0.415476")
    assert parsed.distribution_unit_price == Decimal("0.611012")
    assert parsed.energy_amount == Decimal("69.80")
    assert parsed.distribution_amount == Decimal("102.65")
    assert parsed.public_lighting_brl == Decimal("20.27")
    assert parsed.method == "component_prices"
    assert parsed.rate_brl_kwh == Decimal("1.026488")
    assert parsed.rate_brl_kwh != Decimal("0.310850") + Decimal("0.457170")


def test_full_bill_average_reference_calculation() -> None:
    parsed = extract_copel_bill_text(HEADER + METER + TOTAL)
    assert parsed.method == "full_bill_average"
    assert parsed.rate_brl_kwh == Decimal("192.72") / Decimal("168")
    assert parsed.rate_brl_kwh != Decimal("1.026488")


def test_partial_item_row_uses_fallback() -> None:
    parsed = extract_copel_bill_text(HEADER + ENERGY + METER + TOTAL)
    assert parsed.billed_kwh == 168
    assert parsed.method == "full_bill_average"


def test_invalid_line_amount_uses_fallback_instead_of_bad_unit_price() -> None:
    altered = BILL.replace("0,611012 102,65", "0,211012 102,65")
    parsed = extract_copel_bill_text(altered)
    assert parsed.method == "full_bill_average"
    assert parsed.rate_brl_kwh == Decimal("192.72") / Decimal("168")


def test_if_no_meter_still_uses_two_consistent_item_kwh() -> None:
    parsed = extract_copel_bill_text(BILL.replace(METER, ""))
    assert parsed.billed_kwh == 168
    assert parsed.method == "component_prices"


def test_if_only_one_item_kwh_still_can_fallback() -> None:
    parsed = extract_copel_bill_text(HEADER + ENERGY + TOTAL)
    assert parsed.method == "full_bill_average"
    assert parsed.billed_kwh == 168


def test_only_history_is_not_accepted_as_current_kwh() -> None:
    with pytest.raises(BillImportError, match="consumo faturado"):
        extract_copel_bill_text(HEADER + HISTORY + TOTAL)
