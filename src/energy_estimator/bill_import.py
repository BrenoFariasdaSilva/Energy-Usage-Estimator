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


def _total(text: str) -> Decimal | None:
    """Find the grand total, cross-checking it against a reference-month summary if present."""
    # Restrict to the item-table grand total, not an arbitrary tax base or barcode amount.
    grand_candidates = [
        _decimal(match.group(1)) for match in re.finditer(rf"^\s*TOTAL\s+({_MONEY})(?=\s|$)", text, re.M)
    ]
    summaries = [
        _decimal(match.group(1)) for match in re.finditer(
            rf"^\s*\d{{2}}/\d{{4}}\s+\d{{2}}/\d{{2}}/\d{{4}}\s+R\$\s*({_MONEY})(?=\s|$)", text, re.M
        )
    ]
    if len(set(grand_candidates)) > 1 or len(set(summaries)) > 1:
        raise BillImportError("Há valores totais contraditórios no PDF. Confira a fatura manualmente.")
    grand = _unique(grand_candidates)
    summary = _unique(summaries)
    if grand is not None and summary is not None and abs(grand - summary) > Decimal("0.01"):
        raise BillImportError("O total da tabela e o total do cabeçalho divergem. Confira a fatura manualmente.")
    return grand if grand is not None else summary


def _meter_kwh(text: str) -> Decimal | None:
    """Read billed kWh in the metering row, never the multi-month history chart."""
    values = []
    for line in text.splitlines():
        # The reference Copel layout: CONSUMO kWh TP [previous] [current] [multiplier] [billed].
        match = re.search(
            rf"^\s*\d{{5,}}\s+CONSUMO\s+KWH\s+\w+\s+({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})(?=\s|$)",
            line,
        )
        if match:
            values.append(_decimal(match.group(4)))
    if len(set(values)) > 1:
        raise BillImportError("Há consumos medidos contraditórios no PDF. Confira a fatura manualmente.")
    return _unique(values)


def _public_lighting(text: str) -> Decimal | None:
    values = []
    for match in re.finditer(
        rf"^\s*CONT\s+ILUMIN\s+PUBLICA\s+MUNICIPIO\s+UN\s+{_NUM}\s+({_MONEY})(?=\s|$)",
        text, re.M,
    ):
        values.append(_decimal(match.group(1)))
    return _unique(values)


def extract_copel_bill_text(text: str) -> CopelBill:
    """Parse the *layout-preserving* text of page one of a Copel DANF3E PDF.

    Known taxed TE/TUSD prices take precedence, but only when the item row
    amounts agree with billed kWh. Otherwise use Method 2 (full-bill average)
    if and only if both total and current billed kWh can be established.
    """
    normalized = _normalized(text)
    # Check actual issuer in the header, not merely a stray brand word elsewhere.
    header = normalized[:2600]
    if not ("DANF3E" in header and _PROVIDER.search(header) and _CNPJ.search(header)):
        raise UnsupportedBillError(
            "PDF não reconhecido como fatura DANF3E da Copel Distribuição S.A. "
            "Somente PDFs textuais desse modelo da Copel são suportados."
        )

    month = re.search(r"^\s*(0[1-9]|1[0-2])/(20\d{2})\s+\d{2}/\d{2}/\d{4}\s+R\$", normalized, re.M)
    reference = f"{month.group(1)}/{month.group(2)}" if month else None
    total = _total(normalized)
    energy = _component(normalized, "energy")
    distribution = _component(normalized, "distribution")
    meter = _meter_kwh(normalized)

    # Extract kWh from the invoice's charge rows; require agreement if two rows exist.
    charges = [item.kwh for item in (energy, distribution) if item]
    rows_kwh = _unique(charges)
    if len(charges) == 2 and rows_kwh is None:
        raise BillImportError("Os consumos das linhas de energia e distribuição são diferentes; verifique a fatura.")
    if rows_kwh is not None and meter is not None and rows_kwh != meter:
        raise BillImportError("O consumo da tabela e a leitura do medidor divergem; verifique a fatura.")
    billed_kwh = rows_kwh if rows_kwh is not None else meter

    if total is None or total <= 0 or billed_kwh is None or billed_kwh <= 0:
        raise BillImportError(
            "Não foi possível identificar com segurança o total a pagar e o consumo faturado (kWh) "
            "neste PDF da Copel. Informe os valores manualmente."
        )

    method: Literal["component_prices", "full_bill_average"] = "full_bill_average"
    rate = total / billed_kwh
    if energy and distribution and energy.kwh == distribution.kwh == billed_kwh:
        # Compare the charged value with the tax-inclusive unit price, not with
        # Copel's lower 'Tarifa unit. (R$)' column (excluding some taxes).
        fits = all(
            item.unit_price > 0 and abs(item.unit_price * billed_kwh - item.amount) <= Decimal("0.03")
            for item in (energy, distribution)
        )
        if fits:
            candidate = energy.unit_price + distribution.unit_price
            # A nonsensical price is never accepted just because two rows match.
            if 0 < candidate <= Decimal("1000"):
                rate = candidate
                method = "component_prices"

    if not (Decimal("0") < rate <= Decimal("1000")):
        raise BillImportError("A tarifa calculada está fora da faixa permitida. Confira a fatura manualmente.")

    return CopelBill(
        reference=reference,
        billed_kwh=billed_kwh,
        total_brl=total,
        rate_brl_kwh=rate,
        method=method,
        energy_unit_price=energy.unit_price if energy else None,
        distribution_unit_price=distribution.unit_price if distribution else None,
        energy_amount=energy.amount if energy else None,
        distribution_amount=distribution.amount if distribution else None,
        public_lighting_brl=_public_lighting(normalized),
    )


def parse_copel_pdf(raw: bytes) -> CopelBill:
    """Open a small text-based PDF locally and parse page one only; no OCR."""
    if not isinstance(raw, bytes) or not raw.startswith(b"%PDF-"):
        raise UnreadableBillError("Arquivo inválido: envie um PDF original (não imagem renomeada como .pdf).")
    if len(raw) > MAX_BILL_BYTES:
        raise UnreadableBillError("O PDF excede o limite de 10 MB.")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise UnreadableBillError("PDF protegido por senha. Exporte uma cópia PDF sem proteção.")
        pages = len(reader.pages)
        if not 1 <= pages <= MAX_BILL_PAGES:
            raise UnreadableBillError("São aceitos PDFs de 1 a 6 páginas.")
        first_page = reader.pages[0]
        page_text = (first_page.extract_text(extraction_mode="layout") or "") if "/Contents" in first_page else ""
    except Exception as exc:
        if isinstance(exc, BillImportError):
            raise
        raise UnreadableBillError("Não foi possível ler esse PDF. Verifique se o arquivo está íntegro.") from exc
    if not page_text.strip():
        raise UnreadableBillError(
            "PDF sem texto selecionável (possivelmente digitalizado). Não há OCR; "
            "informe a tarifa ou os valores da fatura manualmente."
        )
    if len(page_text) > MAX_PAGE_TEXT:
        raise UnreadableBillError("O PDF contém texto demais para uma fatura compatível.")
    return extract_copel_bill_text(page_text)
