"""Charts use estimates without inventing numbers or changing calculation units."""

from __future__ import annotations

import pytest

from energy_estimator.calculations import estimate_item
from energy_estimator.charts import (
    cost_by_duration,
    scenario_comparison,
    scenario_energy_donut,
    scenario_monthly_bar,
    scenario_period_bar,
)
from energy_estimator.models import Device, UsageItem


def test_period_charts(fan: Device) -> None:
    """All three period charts expose the correct axis units."""
    est = estimate_item(fan, UsageItem(fan.id, 8), 0.85)
    for period, unit in (("week", "Semanal"), ("month", "Mensal"), ("year", "Anual")):
        fig = scenario_period_bar([est], period)
        assert unit in fig.layout.xaxis.title.text
        assert len(fig.data) == 1
    assert scenario_monthly_bar([est]).layout.xaxis.title.text == "Mensal (R$)"


def test_invalid_chart_period(fan: Device) -> None:
    """Unexpected period keys fail explicitly rather than showing mislabeled data."""
    est = estimate_item(fan, UsageItem(fan.id, 8), 1)
    with pytest.raises(ValueError):
        scenario_period_bar([est], "quarter")


def test_donut_compare_duration(fan: Device) -> None:
    """Composition, comparison and duration charts render standalone Plotly figures."""
    est = estimate_item(fan, UsageItem(fan.id, 2), 1)
    assert len(scenario_energy_donut([est]).data) == 1
    assert len(scenario_comparison([{"Cenário": "Casa", "Mensal (R$)": 12.1}]).data) == 1
    assert len(cost_by_duration([{"Aparelho": "Ventilador", "Custo (R$)": 1.2}]).data) == 1
