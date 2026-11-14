"""Interactive local-first Streamlit dashboard for household electricity costs."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from energy_estimator.calculations import (  # noqa: E402
    cost_for_hours,
    estimate_scenario,
    format_brl,
    format_number,
    hours_from_duration,
    totals,
)
from energy_estimator.charts import (  # noqa: E402
    cost_by_duration,
    scenario_comparison,
    scenario_energy_donut,
    scenario_period_bar,
)
from energy_estimator.models import Device, Scenario, Tariff, UsageItem, new_id  # noqa: E402
from energy_estimator.bill_import import BillImportError, CopelBill, parse_copel_pdf  # noqa: E402
from energy_estimator.presets import example_devices  # noqa: E402
from energy_estimator.storage import JsonStore, StorageError, data_directory, is_browser_runtime  # noqa: E402
from energy_estimator.ui_theme import browser_theme_marker, style_chart, theme_css  # noqa: E402

BROWSER_MODE = is_browser_runtime()

st.set_page_config(page_title="Energy Usage Estimator", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")


STORE = JsonStore(data_directory(ROOT))
try:
    DEVICES, SCENARIOS, TARIFF = STORE.load_all()
    SAVED_THEME = STORE.load_theme()
except StorageError as exc:
    st.error(f"Não foi possível carregar os dados locais: {exc}")
    st.info("Os arquivos não foram alterados. Corrija ou restaure os JSONs na pasta de dados para continuar.")
    st.stop()


def show_success(message: str) -> None:
    """Show a notification that survives the next Streamlit rerun."""
    st.session_state["notification"] = message
    st.rerun()


def save_or_warn(action, success_message: str) -> None:
    """Handle known user-input and file errors without discarding form state silently."""
    try:
        action()
    except (ValueError, StorageError, OSError) as exc:
        st.error(str(exc))
    else:
        show_success(success_message)


def render_chart(fig) -> None:
    """Use a matching Plotly color scheme instead of Streamlit's independent chart theme."""
    st.plotly_chart(style_chart(fig, ACTIVE_THEME), use_container_width=True, theme=None)


def header(title: str, subtitle: str) -> None:
    """Render a consistent dashboard heading."""
    st.title(title)
    st.caption(subtitle)


def device_label(device: Device) -> str:
    """Describe a device in selection controls."""
    return f"{device.name} · {format_number(device.watts, 0)} W"


def copel_pdf_import() -> None:
    """Preview a supported Copel PDF, then apply its parsed rate only after confirmation."""
    with st.expander("Importar fatura da Copel (PDF)", expanded=False):
        st.caption(
            "Suportado: faturas **DANF3E da Copel Distribuição S.A.** em PDF com texto selecionável, "
            "conforme o modelo NF3e testado (até 6 páginas, 10 MB). "
            "Outras distribuidoras, modelos desconhecidos, digitalizações e PDFs com senha não são suportados."
        )
        upload = st.file_uploader("Selecione a fatura original da Copel", type=["pdf"], key="copel_pdf_upload")
        if upload is None:
            return
        try:
            parsed: CopelBill = parse_copel_pdf(upload.getvalue())
        except BillImportError as exc:
            st.error(str(exc))
            st.info("A importação não alterou a tarifa salva. Use a entrada manual abaixo se necessário.")
            return

        st.success("Fatura DANF3E da Copel reconhecida. Confira os valores antes de aplicar.")
        a, b, c = st.columns(3)
        a.metric("Referência", parsed.reference or "Não identificada")
        b.metric("Consumo faturado", f"{format_number(float(parsed.billed_kwh), 2)} kWh")
        c.metric("Total a pagar", format_brl(float(parsed.total_brl)))
        st.write(f"**Método utilizado:** {parsed.method_label}")
        st.metric("Tarifa calculada", f"R$ {format_number(float(parsed.rate_brl_kwh), 6)}/kWh")
        if parsed.energy_unit_price is not None:
            st.write(f"Preço de energia (com tributos): R$ {format_number(float(parsed.energy_unit_price), 6)}/kWh")
        if parsed.distribution_unit_price is not None:
            st.write(f"Preço de distribuição (com tributos): R$ {format_number(float(parsed.distribution_unit_price), 6)}/kWh")
        if parsed.public_lighting_brl is not None:
            st.write(f"Iluminação pública na fatura: {format_brl(float(parsed.public_lighting_brl))}")
        if parsed.method == "full_bill_average":
            st.warning(
                "Os dois preços unitários (energia + distribuição) não puderam ser validados. "
                "Foi aplicada a média da fatura completa: total a pagar ÷ kWh, "
                "que pode incluir iluminação pública e outros encargos."
            )
        else:
            st.caption(
                "Tarifa composta pelos preços unitários COM tributos de energia e distribuição. "
                "O total da conta e o consumo também foram extraídos; iluminação pública não entra na tarifa."
            )
        st.caption("O PDF é processado localmente em memória e não é gravado no diretório de dados.")
        if st.button("Aplicar tarifa extraída", type="primary", key="apply_copel_bill"):
            mode = "direct" if parsed.method == "component_prices" else "bill"
            tariff = Tariff(
                mode=mode,
                direct_rate=float(parsed.rate_brl_kwh) if mode == "direct" else TARIFF.direct_rate,
                bill_amount=float(parsed.total_brl),
                bill_kwh=float(parsed.billed_kwh),
                source="copel_pdf",
                bill_reference=parsed.reference or "",
            )

            def persist() -> None:
                STORE.save_tariff(tariff)
                # The radio has not been instantiated on this run yet.
                st.session_state["tariff_mode_choice"] = mode

            save_or_warn(persist, "Tarifa da fatura Copel salva localmente. Os cenários foram recalculados.")


def tariff_form() -> None:
    """Direct rate, bill-average rate, or imported Copel PDF with user confirmation."""
    st.subheader("Tarifa da energia")
    copel_pdf_import()
    mode = st.radio(
        "Como deseja informar o custo da energia?",
        options=("direct", "bill"),
        format_func=lambda value: "Inserir valor por kWh" if value == "direct" else "Calcular a partir da fatura",
        index=0 if TARIFF.mode == "direct" else 1,
        horizontal=True,
        key="tariff_mode_choice",
    )
    with st.form("tariff_form"):
        if mode == "direct":
            direct = st.number_input(
                "Preço de 1 kWh (R$)", min_value=0.0, max_value=1000.0,
                value=float(TARIFF.direct_rate), step=0.01, format="%.6f",
                help="Valor padrão (sem dados salvos): R$ 1,00/kWh. Não confundir kWh com kW.",
            )
            amount = TARIFF.bill_amount
            kwh = TARIFF.bill_kwh
        else:
            left, right = st.columns(2)
            with left:
                amount = st.number_input(
                    "Valor total da fatura (R$)", min_value=0.0, max_value=10_000_000.0,
                    value=float(TARIFF.bill_amount), step=10.0, format="%.2f",
                )
            with right:
                kwh = st.number_input(
                    "Consumo mostrado na fatura (kWh)", min_value=0.0, max_value=10_000_000.0,
                    value=float(TARIFF.bill_kwh), step=10.0, format="%.2f",
                )
            direct = TARIFF.direct_rate
            if kwh > 0:
                st.info(f"Tarifa média estimada da fatura: **R$ {format_number(amount / kwh, 6)}/kWh**")
            else:
                st.warning("Informe um consumo maior que zero para calcular a tarifa.")
        submitted = st.form_submit_button("Salvar tarifa", type="primary", use_container_width=True)
    if submitted:
        save_or_warn(lambda: STORE.save_tariff(Tariff(mode, float(direct), float(amount), float(kwh))),
                     "Tarifa salva nos arquivos locais.")
    if TARIFF.source == "copel_pdf":
        st.caption(f"Tarifa salva a partir de PDF da Copel"
                   f"{f' — referência {TARIFF.bill_reference}' if TARIFF.bill_reference else ''}.")
    st.caption(
        "A fatura total ÷ kWh resulta em uma **tarifa média efetiva**, não necessariamente no preço marginal "
        "do próximo kWh. Pode incluir iluminação pública, impostos, custos fixos, descontos e ajustes."
    )
