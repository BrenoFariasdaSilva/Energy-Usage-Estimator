"""Conservative, offline extraction of text-based Copel DANF3E electricity bills.

Only known Copel Distribuição S.A. layouts are supported. Do not silently
interpret an unknown utility's PDF, guessed kWh, or a historical consumption
entry as the current invoice. No OCR, network calls, or PDF persistence.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from pypdf import PdfReader

MAX_BILL_BYTES = 10 * 1024 * 1024
MAX_BILL_PAGES = 6
MAX_PAGE_TEXT = 150_000

# These two names and their headings occur on the user's verified Copel NF3e.
_PROVIDER = re.compile(r"\bCOPEL\s+DISTRIBUICAO\s+S\.?\s*A\.?\b")
_CNPJ = re.compile(r"\b04\.?368\.?898\s*/\s*0001\s*-\s*06\b")
_NUM = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
_MONEY = r"(?:\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})"
_COMPONENT_NAMES = {
    "energy": r"ENERGIA\s+ELET(?:RICA)?\s+CONSUMO",
    "distribution": r"ENERGIA\s+ELET(?:RICA)?\s+USO\s+SISTEMA",
}


class BillImportError(ValueError):
    """A PDF cannot be safely recognized or imported."""


class UnsupportedBillError(BillImportError):
    """The PDF is not a supported Copel Distribuição DANF3E bill."""


class UnreadableBillError(BillImportError):
    """The PDF has no usable selectable text or requires a password."""


@dataclass(frozen=True, slots=True)
class _Component:
    """One billed, taxed electricity charge from the invoice's item table."""

    kwh: Decimal
    unit_price: Decimal
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CopelBill:
    """Only non-identifying numeric data extracted from a Copel invoice."""

    reference: str | None
    billed_kwh: Decimal
    total_brl: Decimal
    rate_brl_kwh: Decimal
    method: Literal["component_prices", "full_bill_average"]
    energy_unit_price: Decimal | None = None
    distribution_unit_price: Decimal | None = None
    energy_amount: Decimal | None = None
    distribution_amount: Decimal | None = None
    public_lighting_brl: Decimal | None = None

    @property
    def method_label(self) -> str:
        if self.method == "component_prices":
            return "Preços unitários da Copel (energia + distribuição, com tributos)"
        return "Média da fatura completa (valor total ÷ kWh)"


def _normalized(value: str) -> str:
    """Normalize printable accents for anchored labels without changing numeric punctuation."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value.strip().replace(".", "").replace(",", "."))
    except InvalidOperation as exc:
        raise BillImportError("O PDF contém um valor numérico inválido.") from exc
    if not result.is_finite() or result < 0:
        raise BillImportError("O PDF contém um valor numérico inválido.")
    return result


def _unique(values: list[Decimal]) -> Decimal | None:
    """A conflicting field is ambiguous: never pick a random occurrence."""
    return values[0] if values and all(item == values[0] for item in values) else None


def _component(text: str, name: str) -> _Component | None:
    """Read columns only when the complete expected Copel item row is present."""
    label = _COMPONENT_NAMES[name]
    pattern = re.compile(
        rf"^\s*{label}\s+KWH\s+({_NUM})\s+({_NUM})\s+({_MONEY})(?=\s|$)", re.MULTILINE
    )
    matches = [_Component(*(_decimal(value) for value in match.groups())) for match in pattern.finditer(text)]
    # A duplicated identical row could denote a second charge. Do not use it.
    return matches[0] if len(matches) == 1 else None
