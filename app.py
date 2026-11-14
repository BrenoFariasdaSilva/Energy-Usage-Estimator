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


def duration_inputs(prefix: str) -> tuple[float, int, float]:
    """Offer one-click 1/8/24-hour examples and a customizable duration."""
    choice = st.segmented_control(
        "Horas de funcionamento", ["1 hora", "8 horas", "24 horas", "Personalizado"],
        default="1 hora", key=f"{prefix}_duration", required=True,
    )
    hours = {"1 hora": 1.0, "8 horas": 8.0, "24 horas": 24.0}.get(choice)
    if hours is None:
        hours = st.number_input(
            "Duração personalizada (horas)", min_value=0.0, max_value=8760.0,
            value=3.0, step=0.25, key=f"{prefix}_custom_hours",
        )
    c1, c2 = st.columns(2)
    quantity = c1.number_input(
        "Quantidade de aparelhos", min_value=1, max_value=1000,
        value=1, step=1, key=f"{prefix}_quantity",
    )
    percent = c2.slider(
        "Carga média (%)", min_value=0, max_value=100, value=100, step=5,
        help="100% = potência nominal durante todas as horas. 50% = metade da potência média.",
        key=f"{prefix}_duty",
    )
    return float(hours), int(quantity), percent / 100


def quick_calc() -> None:
    """Show an instant per-hour, 8-hour, 24-hour or custom appliance calculation."""
    st.subheader("Consulta rápida de consumo")
    if not DEVICES:
        st.info("Cadastre um aparelho em 'Aparelhos' ou adicione exemplos para começar.")
        return
    selected_id = st.selectbox(
        "Aparelho", [device.id for device in DEVICES],
        format_func=lambda item: device_label(next(device for device in DEVICES if device.id == item)),
        key="quick_device",
    )
    device = next(item for item in DEVICES if item.id == selected_id)
    hours, quantity, duty = duration_inputs("quick")
    kwh, price = cost_for_hours(device, hours, TARIFF.rate, quantity=quantity, duty_cycle=duty)
    a, b, c = st.columns(3)
    a.metric("Consumo estimado", f"{format_number(kwh, 3)} kWh")
    b.metric("Custo estimado", format_brl(price))
    c.metric("Tarifa aplicada", f"R$ {format_number(TARIFF.rate, 4)}/kWh")
    st.caption("Custo para as horas selecionadas, sem consumo em espera. A carga média ajusta a potência nominal.")
    st.markdown("**Atalhos para o aparelho selecionado**")
    examples = st.columns(3)
    for column, example_hours in zip(examples, (1, 8, 24)):
        _, example_cost = cost_for_hours(device, example_hours, TARIFF.rate, quantity=quantity, duty_cycle=duty)
        column.metric(f"{example_hours} {'hora' if example_hours == 1 else 'horas'}", format_brl(example_cost))


def dashboard_page() -> None:
    """Configure energy pricing and summarize saved scenario estimates."""
    st.markdown(
        """<div class="eue-hero">
        <div class="eue-eyebrow">ENERGY LEARNING WORKSPACE</div>
        <h1>Energy Usage Estimator</h1>
        <p>Explore custos de energia, compare aparelhos e planeje rotinas de consumo.
        Seus aparelhos, cenários e preferências permanecem salvos localmente em JSON.</p>
        </div>""", unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    a.metric("Aparelhos cadastrados", len(DEVICES))
    b.metric("Cenários salvos", len(SCENARIOS))
    c.metric("Tarifa atual", f"R$ {format_number(TARIFF.rate, 4)}/kWh")
    tariff_form()
    st.divider()
    quick_calc()
    st.divider()
    st.subheader("Resumo dos cenários salvos")
    if not SCENARIOS:
        st.info("Nenhum cenário criado. Acesse 'Cenários' para combinar aparelhos e horários de uso.")
        return
    rows = []
    for scenario in SCENARIOS:
        summary = totals(estimate_scenario(scenario, DEVICES, TARIFF.rate))
        rows.append({"Cenário": scenario.name, "Aparelhos": len(scenario.items),
                     "kWh / 30 dias": round(summary["monthly_kwh"], 3),
                     "R$ / 30 dias": round(summary["monthly_cost"], 2)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Um mês equivale a 30 dias; uso em dias da semana é convertido por média de 30/7 semanas.")


def devices_page() -> None:
    """Manage reusable appliances and editable example wattages."""
    header("Aparelhos", "Cadastre a potência em watts de seus eletrônicos e eletrodomésticos.")
    st.warning("As potências de catálogo são apenas ilustrativas. Use a etiqueta, manual ou medidor de tomada para estimativas melhores.", icon="ℹ️")
    if st.button("Adicionar aparelhos de exemplo não cadastrados"):
        pending = example_devices(DEVICES)
        if not pending:
            st.info("Todos os exemplos já estão cadastrados.")
        else:
            def insert_presets() -> None:
                for device in pending:
                    STORE.upsert_device(device)
            save_or_warn(insert_presets, f"{len(pending)} aparelhos de exemplo adicionados.")

    tab_add, tab_edit = st.tabs(["Cadastrar", "Editar ou excluir"])
    with tab_add:
        with st.form("new_device", clear_on_submit=True):
            name = st.text_input("Nome do aparelho", placeholder="Ex.: Computador gamer")
            category = st.text_input("Categoria", value="Informática")
            c1, c2 = st.columns(2)
            watts = c1.number_input("Potência ativa (W)", min_value=0.001, max_value=1_000_000.0,
                                    value=300.0, step=10.0, format="%.3f")
            standby = c2.number_input("Potência em espera (W)", min_value=0.0, max_value=1_000_000.0,
                                      value=0.0, step=0.5, format="%.3f")
            notes = st.text_area("Observações (opcional)", max_chars=500)
            create = st.form_submit_button("Salvar novo aparelho", type="primary")
        if create:
            save_or_warn(lambda: STORE.upsert_device(Device(new_id(), name, category, watts, standby, notes)),
                         "Aparelho cadastrado.")

    with tab_edit:
        if not DEVICES:
            st.info("Ainda não há aparelhos para editar.")
        else:
            chosen_id = st.selectbox("Selecionar aparelho", [device.id for device in DEVICES],
                                     format_func=lambda value: device_label(next(d for d in DEVICES if d.id == value)))
            current = next(device for device in DEVICES if device.id == chosen_id)
            with st.form(f"edit_device_{chosen_id}"):
                name = st.text_input("Nome", value=current.name)
                category = st.text_input("Categoria", value=current.category)
                c1, c2 = st.columns(2)
                watts = c1.number_input("Potência ativa (W)", min_value=0.001, max_value=1_000_000.0,
                                        value=float(current.watts), step=10.0, format="%.3f")
                standby = c2.number_input("Potência em espera (W)", min_value=0.0, max_value=1_000_000.0,
                                          value=float(current.standby_watts), step=0.5, format="%.3f")
                notes = st.text_area("Observações", value=current.notes, max_chars=500)
                update = st.form_submit_button("Atualizar aparelho", type="primary")
            if update:
                save_or_warn(lambda: STORE.upsert_device(Device(current.id, name, category, watts, standby, notes)),
                             "Aparelho atualizado. Cenários vinculados foram recalculados.")
            st.divider()
            confirm = st.checkbox(f"Confirmo a exclusão de '{current.name}'", key=f"delete_device_confirm_{chosen_id}")
            if st.button("Excluir aparelho", disabled=not confirm, key=f"delete_device_{chosen_id}"):
                save_or_warn(lambda: STORE.delete_device(chosen_id), "Aparelho excluído.")
            st.caption("Se o aparelho estiver em um cenário, remova-o do cenário primeiro. A exclusão não ocorre automaticamente.")

    st.divider()
    st.subheader(f"Biblioteca local ({len(DEVICES)})")
    if DEVICES:
        rows = [{"Nome": d.name, "Categoria": d.category, "Potência (W)": d.watts,
                 "Em espera (W)": d.standby_watts, "Observações": d.notes} for d in DEVICES]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def calculator_page() -> None:
    """Compare the same operating duration across all registered appliances."""
    header("Comparador rápido", "Compare quanto custaria ligar cada aparelho por 1, 8, 24 ou mais horas.")
    if not DEVICES:
        st.info("Cadastre aparelhos primeiro.")
        return
    hours, qty, duty = duration_inputs("comparison")
    rows = []
    for device in DEVICES:
        kwh, cost = cost_for_hours(device, hours, TARIFF.rate, quantity=qty, duty_cycle=duty)
        rows.append({"Aparelho": device.name, "Categoria": device.category,
                     "Potência (W)": device.watts, "Energia (kWh)": round(kwh, 4), "Custo (R$)": round(cost, 4)})
    rows.sort(key=lambda item: item["Custo (R$)"], reverse=True)
    st.caption(f"Tarifa: R$ {format_number(TARIFF.rate, 4)}/kWh. Exemplo de uso por {format_number(hours)} horas, sem espera.")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    render_chart(cost_by_duration(rows))
    st.download_button("Baixar comparação (CSV)", rows_csv(rows), "comparacao-aparelhos.csv", "text/csv")
    st.info("Um chuveiro ligado por 24 horas é apenas um cenário matemático. Para uso realista, utilize 'Cenários'.")
