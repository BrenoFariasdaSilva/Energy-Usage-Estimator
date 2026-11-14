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

from energy_estimator.bill_import import BillImportError, CopelBill, parse_copel_pdf  # noqa: E402
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
from energy_estimator.presets import example_devices  # noqa: E402
from energy_estimator.storage import JsonStore, StorageError, data_directory, is_browser_runtime  # noqa: E402
from energy_estimator.ui_theme import browser_theme_marker, style_chart, theme_css  # noqa: E402

BROWSER_MODE = is_browser_runtime()

st.set_page_config(
    page_title="Energy Usage Estimator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
            st.write(
                "Preço de distribuição (com tributos): "
                f"R$ {format_number(float(parsed.distribution_unit_price), 6)}/kWh"
            )
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
                "Preço de 1 kWh (R$)",
                min_value=0.0,
                max_value=1000.0,
                value=float(TARIFF.direct_rate),
                step=0.01,
                format="%.6f",
                help="Valor padrão (sem dados salvos): R$ 1,00/kWh. Não confundir kWh com kW.",
            )
            amount = TARIFF.bill_amount
            kwh = TARIFF.bill_kwh
        else:
            left, right = st.columns(2)
            with left:
                amount = st.number_input(
                    "Valor total da fatura (R$)",
                    min_value=0.0,
                    max_value=10_000_000.0,
                    value=float(TARIFF.bill_amount),
                    step=10.0,
                    format="%.2f",
                )
            with right:
                kwh = st.number_input(
                    "Consumo mostrado na fatura (kWh)",
                    min_value=0.0,
                    max_value=10_000_000.0,
                    value=float(TARIFF.bill_kwh),
                    step=10.0,
                    format="%.2f",
                )
            direct = TARIFF.direct_rate
            if kwh > 0:
                st.info(f"Tarifa média estimada da fatura: **R$ {format_number(amount / kwh, 6)}/kWh**")
            else:
                st.warning("Informe um consumo maior que zero para calcular a tarifa.")
        submitted = st.form_submit_button("Salvar tarifa", type="primary", use_container_width=True)
    if submitted:
        save_or_warn(
            lambda: STORE.save_tariff(Tariff(mode, float(direct), float(amount), float(kwh))),
            "Tarifa salva nos arquivos locais.",
        )
    if TARIFF.source == "copel_pdf":
        st.caption(
            f"Tarifa salva a partir de PDF da Copel"
            f"{f' — referência {TARIFF.bill_reference}' if TARIFF.bill_reference else ''}."
        )
    st.caption(
        "A fatura total ÷ kWh resulta em uma **tarifa média efetiva**, não necessariamente no preço marginal "
        "do próximo kWh. Pode incluir iluminação pública, impostos, custos fixos, descontos e ajustes."
    )


def duration_inputs(prefix: str) -> tuple[float, int, float]:
    """Offer one-click 1/8/24-hour examples and a customizable duration."""
    choice = st.segmented_control(
        "Horas de funcionamento",
        ["1 hora", "8 horas", "24 horas", "Personalizado"],
        default="1 hora",
        key=f"{prefix}_duration",
        required=True,
    )
    hours = {"1 hora": 1.0, "8 horas": 8.0, "24 horas": 24.0}.get(choice)
    if hours is None:
        hours = st.number_input(
            "Duração personalizada (horas)",
            min_value=0.0,
            max_value=8760.0,
            value=3.0,
            step=0.25,
            key=f"{prefix}_custom_hours",
        )
    c1, c2 = st.columns(2)
    quantity = c1.number_input(
        "Quantidade de aparelhos",
        min_value=1,
        max_value=1000,
        value=1,
        step=1,
        key=f"{prefix}_quantity",
    )
    percent = c2.slider(
        "Carga média (%)",
        min_value=0,
        max_value=100,
        value=100,
        step=5,
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
        "Aparelho",
        [device.id for device in DEVICES],
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
        </div>""",
        unsafe_allow_html=True,
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
        rows.append(
            {
                "Cenário": scenario.name,
                "Aparelhos": len(scenario.items),
                "kWh / 30 dias": round(summary["monthly_kwh"], 3),
                "R$ / 30 dias": round(summary["monthly_cost"], 2),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Um mês equivale a 30 dias; uso em dias da semana é convertido por média de 30/7 semanas.")


def devices_page() -> None:
    """Manage reusable appliances and editable example wattages."""
    header("Aparelhos", "Cadastre a potência em watts de seus eletrônicos e eletrodomésticos.")
    st.warning(
        "As potências de catálogo são apenas ilustrativas. Use a etiqueta, manual ou medidor de "
        "tomada para estimativas melhores.",
        icon="ℹ️",
    )
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
            watts = c1.number_input(
                "Potência ativa (W)", min_value=0.001, max_value=1_000_000.0, value=300.0, step=10.0, format="%.3f"
            )
            standby = c2.number_input(
                "Potência em espera (W)", min_value=0.0, max_value=1_000_000.0, value=0.0, step=0.5, format="%.3f"
            )
            notes = st.text_area("Observações (opcional)", max_chars=500)
            create = st.form_submit_button("Salvar novo aparelho", type="primary")
        if create:
            save_or_warn(
                lambda: STORE.upsert_device(Device(new_id(), name, category, watts, standby, notes)),
                "Aparelho cadastrado.",
            )

    with tab_edit:
        if not DEVICES:
            st.info("Ainda não há aparelhos para editar.")
        else:
            chosen_id = st.selectbox(
                "Selecionar aparelho",
                [device.id for device in DEVICES],
                format_func=lambda value: device_label(next(d for d in DEVICES if d.id == value)),
            )
            current = next(device for device in DEVICES if device.id == chosen_id)
            with st.form(f"edit_device_{chosen_id}"):
                name = st.text_input("Nome", value=current.name)
                category = st.text_input("Categoria", value=current.category)
                c1, c2 = st.columns(2)
                watts = c1.number_input(
                    "Potência ativa (W)",
                    min_value=0.001,
                    max_value=1_000_000.0,
                    value=float(current.watts),
                    step=10.0,
                    format="%.3f",
                )
                standby = c2.number_input(
                    "Potência em espera (W)",
                    min_value=0.0,
                    max_value=1_000_000.0,
                    value=float(current.standby_watts),
                    step=0.5,
                    format="%.3f",
                )
                notes = st.text_area("Observações", value=current.notes, max_chars=500)
                update = st.form_submit_button("Atualizar aparelho", type="primary")
            if update:
                save_or_warn(
                    lambda: STORE.upsert_device(Device(current.id, name, category, watts, standby, notes)),
                    "Aparelho atualizado. Cenários vinculados foram recalculados.",
                )
            st.divider()
            confirm = st.checkbox(f"Confirmo a exclusão de '{current.name}'", key=f"delete_device_confirm_{chosen_id}")
            if st.button("Excluir aparelho", disabled=not confirm, key=f"delete_device_{chosen_id}"):
                save_or_warn(lambda: STORE.delete_device(chosen_id), "Aparelho excluído.")
            st.caption(
                "Se o aparelho estiver em um cenário, remova-o do cenário primeiro. "
                "A exclusão não ocorre automaticamente."
            )

    st.divider()
    st.subheader(f"Biblioteca local ({len(DEVICES)})")
    if DEVICES:
        rows = [
            {
                "Nome": d.name,
                "Categoria": d.category,
                "Potência (W)": d.watts,
                "Em espera (W)": d.standby_watts,
                "Observações": d.notes,
            }
            for d in DEVICES
        ]
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
        rows.append(
            {
                "Aparelho": device.name,
                "Categoria": device.category,
                "Potência (W)": device.watts,
                "Energia (kWh)": round(kwh, 4),
                "Custo (R$)": round(cost, 4),
            }
        )
    rows.sort(key=lambda item: item["Custo (R$)"], reverse=True)
    st.caption(
        f"Tarifa: R$ {format_number(TARIFF.rate, 4)}/kWh. Exemplo de uso por {format_number(hours)} horas, sem espera."
    )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    render_chart(cost_by_duration(rows))
    st.download_button("Baixar comparação (CSV)", rows_csv(rows), "comparacao-aparelhos.csv", "text/csv")
    st.info("Um chuveiro ligado por 24 horas é apenas um cenário matemático. Para uso realista, utilize 'Cenários'.")


def rows_csv(rows: list[dict[str, object]]) -> bytes:
    """Return a UTF-8 CSV with an Excel-friendly BOM for Portuguese text."""
    if not rows:
        return b""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def scenario_select() -> Scenario | None:
    """Select an existing scenario or choose the new-scenario editor."""
    options = ["__new__", *[scenario.id for scenario in SCENARIOS]]
    created_id = st.session_state.pop("next_scenario_id", None)
    if created_id in options:
        st.session_state["scenario_pick"] = created_id
    selected = st.selectbox(
        "Cenário",
        options,
        key="scenario_pick",
        format_func=lambda item: (
            "+ Criar novo cenário"
            if item == "__new__"
            else next(scenario.name for scenario in SCENARIOS if scenario.id == item)
        ),
    )
    return next((scenario for scenario in SCENARIOS if scenario.id == selected), None)


def scenario_metadata(scenario: Scenario | None) -> None:
    """Create or rename a scenario while preserving saved schedules."""
    with st.form("scenario_details"):
        name = st.text_input(
            "Nome do cenário", value=scenario.name if scenario else "", placeholder="Ex.: Casa durante a semana"
        )
        description = st.text_area(
            "Descrição (opcional)", value=scenario.description if scenario else "", max_chars=500
        )
        submitted = st.form_submit_button("Salvar cenário", type="primary")
    if submitted:
        try:
            updated = Scenario(
                scenario.id if scenario else new_id(), name, description, scenario.items if scenario else tuple()
            )
            STORE.upsert_scenario(updated)
        except (ValueError, StorageError) as exc:
            st.error(str(exc))
        else:
            st.session_state["next_scenario_id"] = updated.id
            show_success("Cenário salvo.")


def scenario_item_editor(scenario: Scenario) -> None:
    """Add or update a selected appliance's weekday and average-load schedule."""
    st.subheader("Programação dos aparelhos")
    if not DEVICES:
        st.info("Cadastre ao menos um aparelho antes de configurar o uso.")
        return
    selected_id = st.selectbox(
        "Aparelho a adicionar ou editar",
        [device.id for device in DEVICES],
        format_func=lambda value: device_label(next(d for d in DEVICES if d.id == value)),
        key=f"scenario_device_{scenario.id}",
    )
    device = next(d for d in DEVICES if d.id == selected_id)
    stored = next((item for item in scenario.items if item.device_id == selected_id), None)
    time_unit = st.segmented_control(
        "Unidade do tempo de uso",
        ["Horas", "Minutos"],
        default="Horas",
        required=True,
        key=f"scenario_time_unit_{scenario.id}_{selected_id}",
        help="Use minutos para durações curtas, como 10 ou 15 minutos de chuveiro.",
    )
    with st.form(f"item_form_{scenario.id}_{selected_id}_{time_unit}"):
        c1, c2, c3 = st.columns(3)
        if time_unit == "Minutos":
            duration = c1.number_input(
                "Minutos por dia",
                min_value=0.0,
                max_value=1440.0,
                value=float(stored.hours_per_day * 60 if stored else 30),
                step=5.0,
                format="%.2f",
            )
        else:
            duration = c1.number_input(
                "Horas por dia",
                min_value=0.0,
                max_value=24.0,
                value=float(stored.hours_per_day if stored else 2),
                step=0.25,
                format="%.4f",
            )
        days = c2.number_input(
            "Dias por semana", min_value=1, max_value=7, value=int(stored.days_per_week if stored else 7), step=1
        )
        quantity = c3.number_input(
            "Quantidade", min_value=1, max_value=1000, value=int(stored.quantity if stored else 1), step=1
        )
        duty = st.slider(
            "Carga média / ciclo de funcionamento (%)",
            min_value=0,
            max_value=100,
            value=round(stored.duty_cycle * 100) if stored else 100,
            step=1,
            help="Útil para aparelhos cuja potência oscila (PC, geladeira, ar-condicionado). "
            "Use a fração de potência média, não uma garantia de consumo real.",
        )
        standby = st.checkbox(
            f"Incluir consumo em espera de {format_number(device.standby_watts, 2)} W nas demais horas da semana",
            value=stored.include_standby if stored else False,
            help=(
                "Quando marcado, o aparelho fica em espera durante 168 - horas de uso da semana, "
                "inclusive nos dias sem uso."
            ),
        )
        submit = st.form_submit_button("Atualizar uso" if stored else "Adicionar ao cenário", type="primary")
    if submit:

        def save_schedule() -> None:
            hours = hours_from_duration(float(duration), "minutes" if time_unit == "Minutos" else "hours")
            new_item = UsageItem(selected_id, hours, int(days), int(quantity), duty / 100, standby)
            updated = Scenario(
                scenario.id,
                scenario.name,
                scenario.description,
                tuple(item for item in scenario.items if item.device_id != selected_id) + (new_item,),
            )
            STORE.upsert_scenario(updated)

        save_or_warn(save_schedule, "Programação salva no cenário.")


def scenario_results(scenario: Scenario) -> None:
    """Summarize scenario outputs with breakdown, charts and a CSV export."""
    if not scenario.items:
        st.info("Adicione aparelhos acima para gerar uma projeção semanal, mensal e anual.")
        return
    st.divider()
    st.subheader("Projeção do cenário")
    estimated = estimate_scenario(scenario, DEVICES, TARIFF.rate)
    summary = totals(estimated)
    a, b, c, d = st.columns(4)
    a.metric("Por semana", format_brl(summary["weekly_cost"]))
    b.metric("Por 30 dias", format_brl(summary["monthly_cost"]))
    c.metric("Por 365 dias", format_brl(summary["annual_cost"]))
    d.metric("Energia / 30 dias", f"{format_number(summary['monthly_kwh'], 2)} kWh")

    rows = []
    for item, estimate in zip(scenario.items, estimated):
        rows.append(
            {
                "Aparelho": estimate.device_name,
                "Horas/dia": item.hours_per_day,
                "Dias/semana": item.days_per_week,
                "Quantidade": item.quantity,
                "Carga (%)": round(item.duty_cycle * 100, 1),
                "Espera": "Sim" if item.include_standby else "Não",
                "kWh/semana": round(estimate.weekly_kwh, 3),
                "kWh/30 dias": round(estimate.monthly_kwh, 3),
                "R$/semana": round(estimate.weekly_cost, 2),
                "R$/30 dias": round(estimate.monthly_cost, 2),
                "R$/365 dias": round(estimate.annual_cost, 2),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.download_button(
        "Exportar itens e valores (CSV)",
        rows_csv(rows),
        f"cenario-{scenario.id}.csv",
        "text/csv",
        key=f"csv_{scenario.id}",
    )
    view = st.segmented_control(
        "Período dos gráficos de custo",
        ["Semana", "30 dias", "365 dias"],
        default="30 dias",
        required=True,
        key=f"scenario_chart_period_{scenario.id}",
    )
    period = {"Semana": "week", "30 dias": "month", "365 dias": "year"}[view]
    left, right = st.columns(2)
    with left:
        render_chart(scenario_period_bar(estimated, period))
    with right:
        if any(row.monthly_kwh > 0 for row in estimated):
            render_chart(scenario_energy_donut(estimated))
        else:
            st.info("Não há energia positiva para apresentar no gráfico de participação.")
    st.caption(
        "Fórmula semanal: (W × horas/dia × dias/semana × quantidade × carga média) / 1.000; "
        "se habilitada, espera = W de espera × (168 − horas ativas/semana) × quantidade / 1.000. "
        "Mês = semana × 30/7; ano = semana × 365/7."
    )


def scenarios_page() -> None:
    """Build, edit, compare and delete persistent multi-device schedules."""
    header(
        "Cenários de uso",
        "Combine aparelhos, quantidade, horas por dia e dias por semana. Os cenários ficam salvos em JSON.",
    )
    scenario = scenario_select()
    scenario_metadata(scenario)
    if scenario is None:
        st.info("Salve o novo cenário para começar a adicionar aparelhos.")
        return
    scenario_item_editor(scenario)
    if scenario.items:
        st.subheader("Aparelhos do cenário")
        known = {device.id: device for device in DEVICES}
        for item in scenario.items:
            left, right = st.columns([5, 1], vertical_alignment="center")
            left.write(
                f"**{known[item.device_id].name}** — {format_number(item.hours_per_day)} h/dia, "
                f"{item.days_per_week} dias/semana, {item.quantity} un."
            )
            if right.button("Remover", key=f"remove_item_{scenario.id}_{item.device_id}"):
                updated = Scenario(
                    scenario.id,
                    scenario.name,
                    scenario.description,
                    tuple(other for other in scenario.items if other.device_id != item.device_id),
                )
                save_or_warn(lambda: STORE.upsert_scenario(updated), "Aparelho removido do cenário.")
    scenario_results(scenario)
    st.divider()
    confirm = st.checkbox(
        f"Quero excluir definitivamente o cenário '{scenario.name}'",
        key=f"del_scn_ok_{scenario.id}",
    )
    if st.button("Excluir cenário", disabled=not confirm, key=f"del_scn_{scenario.id}"):

        def delete_selected() -> None:
            STORE.delete_scenario(scenario.id)
            st.session_state["next_scenario_id"] = "__new__"

        save_or_warn(delete_selected, "Cenário excluído. Os aparelhos cadastrados foram preservados.")


def comparison_page() -> None:
    """Contrast saved scenarios and estimate savings from changing habits."""
    header("Comparação de cenários", "Compare alternativas e observe o impacto mensal e anual dos hábitos de uso.")
    if not SCENARIOS:
        st.info("Salve cenários primeiro.")
        return
    rows: list[dict[str, float | str]] = []
    for scenario in SCENARIOS:
        amount = totals(estimate_scenario(scenario, DEVICES, TARIFF.rate))
        rows.append(
            {
                "Cenário": scenario.name,
                "Semanal (R$)": round(amount["weekly_cost"], 2),
                "Mensal (R$)": round(amount["monthly_cost"], 2),
                "Anual (R$)": round(amount["annual_cost"], 2),
                "Mensal (kWh)": round(amount["monthly_kwh"], 3),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if any(row["Mensal (R$)"] > 0 for row in rows):
        render_chart(scenario_comparison(rows))
    st.download_button("Baixar comparação (CSV)", rows_csv(rows), "comparacao-cenarios.csv", "text/csv")
    if len(SCENARIOS) > 1:
        st.subheader("Diferença entre alternativas")
        left, right = st.columns(2)
        ids = [item.id for item in SCENARIOS]
        baseline_id = left.selectbox(
            "Cenário atual",
            ids,
            format_func=lambda item: next(s.name for s in SCENARIOS if s.id == item),
        )
        candidate_id = right.selectbox(
            "Cenário alternativo",
            ids,
            index=1,
            format_func=lambda item: next(s.name for s in SCENARIOS if s.id == item),
        )
        if baseline_id == candidate_id:
            st.info("Selecione dois cenários diferentes.")
        else:
            baseline = next(s for s in SCENARIOS if s.id == baseline_id)
            candidate = next(s for s in SCENARIOS if s.id == candidate_id)
            before = totals(estimate_scenario(baseline, DEVICES, TARIFF.rate))
            after = totals(estimate_scenario(candidate, DEVICES, TARIFF.rate))
            delta = before["monthly_cost"] - after["monthly_cost"]
            st.metric(
                "Economia mensal estimada (positivo = economia)", f"{'-' if delta < 0 else ''}{format_brl(abs(delta))}"
            )
            st.metric(
                "Economia anual estimada",
                f"{'-' if delta < 0 else ''}{format_brl(abs(before['annual_cost'] - after['annual_cost']))}",
            )
    st.caption("Cenários usam a mesma tarifa atualmente salva. Alterá-la recalcula automaticamente todos os valores.")


def storage_page() -> None:
    """Explain automatic persistence and offer explicit local checkpoints and export/import."""
    header("Dados e backups", "Salvamento automático nos arquivos JSON, com cópias de segurança manuais e exportação.")
    st.markdown(
        '<div class="eue-status"><strong>Salvamento automático ativado.</strong> '
        "Cada cadastro, atualização, exclusão ou tarifa confirmada é gravada em JSON imediatamente. "
        "Os campos ainda não enviados nos formulários não são salvos.</div>",
        unsafe_allow_html=True,
    )
    if BROWSER_MODE:
        st.info(
            "Nesta versão do GitHub Pages, seus JSONs são armazenados no IndexedDB deste navegador. "
            "Eles não são compartilhados com outros visitantes e não são enviados a um servidor da aplicação. "
            "Use 'Baixar backup completo (JSON)' para manter uma cópia fora do navegador."
        )
        st.caption("Caminho virtual no navegador (não é uma pasta no seu computador):")
    else:
        st.caption("Todos os dados ficam na pasta abaixo, no computador que executa a aplicação:")
    st.code(str(STORE.directory), language="text")
    st.markdown(
        "Arquivos: `devices.json`, `scenarios.json` e `settings.json` (tarifa e tema). "
        "Arquivos de segurança: `backups/`."
    )
    st.subheader("Salvar manualmente")
    st.write(
        "Crie agora um ponto de restauração. O aplicativo regrava os três JSONs "
        "e mantém uma cópia com data e hora em `backups/`, sem substituir backups anteriores."
    )
    if st.button("Salvar dados agora (JSON + backup local)", key="manual_save_now", type="primary"):
        try:
            path = STORE.save_now()
        except (ValueError, StorageError, OSError) as exc:
            st.error(str(exc))
        else:
            show_success(f"Dados gravados e backup manual criado: {path.name}")

    st.divider()
    st.subheader("Exportar")
    st.download_button(
        "Baixar backup completo (JSON)",
        STORE.backup_bytes(),
        "energy-usage-estimator-backup.json",
        "application/json",
        key="download_full_backup",
    )
    st.caption(
        "O download salva uma cópia onde você escolher no navegador; não altera os JSONs nem substitui o backup local."
    )
    st.divider()
    st.subheader("Restaurar backup")
    upload = st.file_uploader("Arquivo JSON exportado por este aplicativo", type=["json"], key="import_file")
    confirm = st.checkbox("Entendo que a importação substituirá meus aparelhos, cenários, tarifa e tema atuais.")
    if st.button("Importar e substituir os dados", disabled=upload is None or not confirm):
        try:
            backup_path = STORE.restore_backup(upload.getvalue())
        except (ValueError, StorageError, OSError) as exc:
            st.error(str(exc))
        else:
            # Widget state from the old appearance must not override imported preference.
            st.session_state.pop("appearance_choice", None)
            show_success(f"Dados importados. Cópia de segurança anterior: {backup_path.name}")
    st.divider()
    st.subheader("Privacidade")
    if BROWSER_MODE:
        st.markdown(
            "No GitHub Pages, o Python executa **dentro do navegador** (Stlite/WebAssembly). "
            "Os arquivos ficam no armazenamento IndexedDB **deste navegador e desta origem**. "
            "O PDF é processado em memória local e não é enviado a um servidor da aplicação. "
            "Limpar dados do site, usar navegação anônima ou outro navegador pode apagar ou ocultar os dados. "
            "Exporte um backup JSON regularmente. O navegador precisa baixar componentes de terceiros "
            "(Stlite/Pyodide/dependências) para executar a aplicação."
        )
    else:
        st.markdown(
            "O Streamlit grava os arquivos **no computador que executa o servidor Python**, não necessariamente no "
            "navegador. Este aplicativo é destinado a uso **local e individual**. Não publique uma instância aberta "
            "na internet com dados pessoais: não há autenticação nem separação entre usuários. "
            "Não enviamos dados para serviços externos pelo código do aplicativo."
        )


PAGES = ("Início", "Aparelhos", "Calculadora", "Cenários", "Comparações", "Dados e backups")
with st.sidebar:
    st.title("Energy Usage Estimator")
    st.caption("Painel de estimativas de eletricidade")
    selected_theme = st.segmented_control(
        "Aparência",
        ("light", "dark"),
        default=SAVED_THEME,
        format_func=lambda value: "☀ Claro" if value == "light" else "◐ Escuro",
        required=True,
        key="appearance_choice",
    )
    if selected_theme != SAVED_THEME:
        try:
            STORE.save_theme(selected_theme)
        except (ValueError, StorageError, OSError) as exc:
            st.error(f"Não foi possível salvar o tema: {exc}")
            ACTIVE_THEME = SAVED_THEME
        else:
            ACTIVE_THEME = selected_theme
    else:
        ACTIVE_THEME = SAVED_THEME
    st.divider()
    page = st.radio("Menu", PAGES, key="page_selector")
    st.divider()
    st.metric("Tarifa atual", f"R$ {format_number(TARIFF.rate, 4)}/kWh")
    if TARIFF.source == "copel_pdf":
        st.caption(
            "Origem: PDF Copel (energia + distribuição)"
            if TARIFF.mode == "direct"
            else "Origem: PDF Copel (total ÷ kWh)"
        )
    else:
        st.caption("Origem: valor informado" if TARIFF.mode == "direct" else "Origem: fatura ÷ consumo")
    st.caption(f"{len(DEVICES)} aparelhos · {len(SCENARIOS)} cenários")
    st.caption(
        "JSON salvo neste navegador · exporte backups"
        if BROWSER_MODE
        else "Salvamento automático ativo · backup manual em Dados e backups"
    )

# Native Streamlit uses its normal injected stylesheet. On static Pages the host
# provides a persistent stylesheet and synchronizes the actual segmented selection;
# injecting a second stylesheet into Stlite caused theme conflicts on reruns.
st.html(browser_theme_marker(ACTIVE_THEME) if BROWSER_MODE else theme_css(ACTIVE_THEME))

if "notification" in st.session_state:
    st.success(st.session_state.pop("notification"))

if page == "Início":
    dashboard_page()
elif page == "Aparelhos":
    devices_page()
elif page == "Calculadora":
    calculator_page()
elif page == "Cenários":
    scenarios_page()
elif page == "Comparações":
    comparison_page()
else:
    storage_page()
