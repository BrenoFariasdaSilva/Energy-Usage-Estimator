"""Copel DANF3E regression tests. No private bills are included in the repository."""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfWriter

from energy_estimator.bill_import import (
    BillImportError,
    UnreadableBillError,
    UnsupportedBillError,
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


def test_conflicting_meter_and_item_kwh_are_rejected() -> None:
    with pytest.raises(BillImportError, match="divergem"):
        extract_copel_bill_text(BILL.replace("2156 2324 1 168", "2156 2324 1 169"))


def test_conflicting_energy_distribution_quantities_rejected() -> None:
    with pytest.raises(BillImportError, match="diferentes"):
        extract_copel_bill_text(BILL.replace("USO SISTEMA kWh 168", "USO SISTEMA kWh 167"))


def test_missing_bill_total_rejected_even_with_energy_prices() -> None:
    with pytest.raises(BillImportError, match="total a pagar"):
        extract_copel_bill_text(BILL.replace(TOTAL, "").replace("11/2026 25/12/2026 R$192,72", "11/2026"))


def test_header_only_total_can_support_fallback() -> None:
    parsed = extract_copel_bill_text(HEADER + METER)
    assert parsed.method == "full_bill_average"
    assert parsed.total_brl == Decimal("192.72")


def test_conflicting_header_and_total_are_rejected() -> None:
    with pytest.raises(BillImportError, match="divergem"):
        extract_copel_bill_text(BILL.replace(TOTAL, "TOTAL 199,00\n"))


def test_public_lighting_does_not_change_direct_unit_rate() -> None:
    a = extract_copel_bill_text(BILL)
    b = extract_copel_bill_text(BILL.replace(LIGHT, ""))
    assert a.rate_brl_kwh == b.rate_brl_kwh


def test_large_values_with_brazilian_thousands_separators() -> None:
    txt = (
        HEADER.replace("R$192,72", "R$1.200,00")
        + "ENERGIA ELET CONSUMO kWh 1.000 0,400000 400,00\n"
        + "ENERGIA ELET USO SISTEMA kWh 1.000 0,500000 500,00\n"
        + "TOTAL 1.200,00\n"
    )
    parsed = extract_copel_bill_text(txt)
    assert parsed.billed_kwh == 1000
    assert parsed.total_brl == 1200
    assert parsed.rate_brl_kwh == Decimal("0.9")


def test_duplicate_charge_rows_do_not_become_validated_price() -> None:
    parsed = extract_copel_bill_text(HEADER + ENERGY + DISTRIBUTION + DISTRIBUTION + METER + TOTAL)
    assert parsed.method == "full_bill_average"


@pytest.mark.parametrize(
    "header",
    [
        "DANF3E\nEnel Distribuicao\nCNPJ 61.695.227/0001-93\nCopel is mentioned in the footer\n",
        "DANF3E\nCopel\n11/2026\n",
        "COPEL DISTRIBUICAO S.A.\nCNPJ 04.368.898/0001-06\n",
        "DANF3E\nCOPEL DISTRIBUICAO S.A.\nCNPJ 99.999.999/0001-99\n",
    ],
)
def test_unsupported_or_unverified_provider_is_rejected(header: str) -> None:
    with pytest.raises(UnsupportedBillError, match="Somente PDFs"):
        extract_copel_bill_text(header + ENERGY + DISTRIBUTION + TOTAL)


def test_no_private_pdf_needed_to_exercise_real_pdf_extraction() -> None:
    data = (Path(__file__).parent / "fixtures" / "copel-danf3e-synthetic.pdf").read_bytes()
    parsed = parse_copel_pdf(data)
    assert parsed.reference == "01/2026"
    assert parsed.method == "component_prices"
    assert parsed.total_brl == Decimal("120")
    assert parsed.billed_kwh == 100
    assert parsed.rate_brl_kwh == Decimal("1")


def test_invalid_or_renamed_image_rejected() -> None:
    for raw in (b"", b"not a PDF", b"\x89PNG\r\n\x1a\n"):
        with pytest.raises(UnreadableBillError, match="PDF original"):
            parse_copel_pdf(raw)


def test_oversized_pdf_rejected() -> None:
    with pytest.raises(UnreadableBillError, match="10 MB"):
        parse_copel_pdf(b"%PDF-1.7\n" + b" " * (10 * 1024 * 1024))


def test_corrupt_pdf_rejected_without_crashing() -> None:
    with pytest.raises(UnreadableBillError, match="ler esse PDF"):
        parse_copel_pdf(b"%PDF-1.7\ninvalid")


def test_scan_without_text_rejected_with_clear_message() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(UnreadableBillError, match="sem texto selecionável"):
        parse_copel_pdf(output.getvalue())


def test_password_protected_pdf_rejected() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt("password")
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(UnreadableBillError, match="protegido por senha"):
        parse_copel_pdf(output.getvalue())


def test_too_many_pages_rejected() -> None:
    writer = PdfWriter()
    for _ in range(7):
        writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(UnreadableBillError, match="1 a 6 páginas"):
        parse_copel_pdf(output.getvalue())


def test_new_default_is_one_real_and_old_saved_data_remains_unchanged(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    assert Tariff().rate == 1.0
    assert store.load_tariff().rate == 1.0
    assert not (tmp_path / "settings.json").exists()
    store.save_tariff(Tariff(direct_rate=0.85))
    assert JsonStore(tmp_path).load_tariff().rate == 0.85


def test_imported_direct_tariff_persists_metadata_and_totals(tmp_path: Path) -> None:
    parsed = extract_copel_bill_text(BILL)
    imported = Tariff(
        mode="direct",
        direct_rate=float(parsed.rate_brl_kwh),
        bill_amount=float(parsed.total_brl),
        bill_kwh=float(parsed.billed_kwh),
        source="copel_pdf",
        bill_reference=parsed.reference or "",
    )
    store = JsonStore(tmp_path)
    store.save_tariff(imported)
    assert JsonStore(tmp_path).load_tariff() == imported
    assert '"source": "copel_pdf"' in store.backup_bytes().decode()
    assert '"bill_reference": "11/2026"' in store.backup_bytes().decode()
    assert "CPF" not in store.backup_bytes().decode()


def test_imported_full_bill_tariff_persists_correct_mode(tmp_path: Path) -> None:
    parsed = extract_copel_bill_text(HEADER + METER + TOTAL)
    imported = Tariff(
        mode="bill",
        direct_rate=1.0,
        bill_amount=float(parsed.total_brl),
        bill_kwh=float(parsed.billed_kwh),
        source="copel_pdf",
        bill_reference="11/2026",
    )
    store = JsonStore(tmp_path)
    store.save_tariff(imported)
    loaded = store.load_tariff()
    assert loaded.mode == "bill"
    assert loaded.rate == pytest.approx(192.72 / 168)


def test_old_format_backup_is_compatible(tmp_path: Path) -> None:
    """v1 JSON lacks source/reference and must still load unchanged."""
    import json

    (tmp_path / "settings.json").write_text(
        json.dumps(
            {"schema_version": 1, "tariff": {"mode": "direct", "direct_rate": 0.85, "bill_amount": 0, "bill_kwh": 0}}
        ),
        encoding="utf-8",
    )
    assert JsonStore(tmp_path).load_tariff() == Tariff(direct_rate=0.85)


def test_invalid_source_or_reference_cannot_be_saved() -> None:
    with pytest.raises(ValueError, match="Origem"):
        Tariff(source="unknown")
    with pytest.raises(ValueError, match="Referência"):
        Tariff(bill_reference="not-a-month")


def test_contradictory_duplicate_totals_must_not_silently_select_one() -> None:
    bad = BILL + "TOTAL 999,00\n"
    with pytest.raises(BillImportError, match="contraditórios"):
        extract_copel_bill_text(bad)


def test_contradictory_meter_rows_must_not_silently_select_one() -> None:
    bad = BILL + "0045158902 CONSUMO kWh TP 2156 2325 1 169\n"
    with pytest.raises(BillImportError, match="contraditórios"):
        extract_copel_bill_text(bad)
