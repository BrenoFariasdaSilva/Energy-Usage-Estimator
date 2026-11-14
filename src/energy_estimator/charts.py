"""Plotly visualization factories used by the Streamlit dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .calculations import UsageEstimate

PALETTE = ["#0284c7", "#0d9488", "#7c3aed", "#ea580c", "#db2777", "#16a34a"]


def _polish(fig: go.Figure, *, title: str, height: int = 370) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left"),
        height=height,
        margin=dict(l=12, r=12, t=54, b=12),
        legend_title_text="",
        hoverlabel=dict(namelength=-1),
    )
    return fig


def scenario_period_bar(estimated: list[UsageEstimate], period: str = "month") -> go.Figure:
    """Rank devices by cost for a week, a 30-day month or a 365-day year."""
    columns = {
        "week": ("weekly_cost", "Semanal (R$)", "Gasto semanal por aparelho"),
        "month": ("monthly_cost", "Mensal (R$)", "Gasto mensal por aparelho"),
        "year": ("annual_cost", "Anual (R$)", "Gasto anual por aparelho"),
    }
    if period not in columns:
        raise ValueError(f"Período não reconhecido: {period}")
    attribute, label, title = columns[period]
    df = pd.DataFrame(
        [{"Aparelho": item.device_name, label: getattr(item, attribute)} for item in estimated]
    ).sort_values(label, ascending=True)
    fig = px.bar(df, x=label, y="Aparelho", orientation="h", color="Aparelho",
                 color_discrete_sequence=PALETTE, text_auto=".2f")
    fig.update_layout(showlegend=False)
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _polish(fig, title=title, height=max(310, min(650, 80 + 42 * len(df))))


def scenario_monthly_bar(estimated: list[UsageEstimate]) -> go.Figure:
    """Keep a convenience alias for the common 30-day scenario plot."""
    return scenario_period_bar(estimated, "month")


def scenario_energy_donut(estimated: list[UsageEstimate]) -> go.Figure:
    """Show the estimated energy share of each scenario device."""
    df = pd.DataFrame([{"Aparelho": item.device_name, "kWh/mês": item.monthly_kwh} for item in estimated])
    fig = px.pie(df, values="kWh/mês", names="Aparelho", hole=0.55, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent", hovertemplate="%{label}: %{value:.2f} kWh (%{percent})<extra></extra>")
    return _polish(fig, title="Participação no consumo mensal")


def scenario_comparison(rows: list[dict[str, float | str]]) -> go.Figure:
    """Compare saved scenarios using estimated monthly costs."""
    df = pd.DataFrame(rows).sort_values("Mensal (R$)", ascending=False)
    fig = px.bar(df, x="Cenário", y="Mensal (R$)", color="Cenário", text_auto=".2f",
                 color_discrete_sequence=PALETTE)
    fig.update_layout(showlegend=False)
    return _polish(fig, title="Comparação de cenários — custo por 30 dias")


def cost_by_duration(device_rows: list[dict[str, float | str]]) -> go.Figure:
    """Compare continuous-use cost across devices for a selected duration."""
    df = pd.DataFrame(device_rows).sort_values("Custo (R$)", ascending=False)
    fig = px.bar(df, x="Aparelho", y="Custo (R$)", color="Aparelho",
                 color_discrete_sequence=PALETTE)
    fig.update_layout(showlegend=False)
    return _polish(fig, title="Comparação por tempo de uso")
