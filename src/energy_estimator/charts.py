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
