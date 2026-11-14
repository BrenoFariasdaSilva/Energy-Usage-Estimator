"""Correctness tests for physical units, periods, money and input validation."""

from __future__ import annotations

import math

import pytest

from energy_estimator.calculations import (
    cost_for_hours,
    energy_kwh,
    estimate_item,
    estimate_scenario,
    format_brl,
    format_number,
    hours_from_duration,
    totals,
)
from energy_estimator.models import Device, Scenario, UsageItem


def test_one_eight_twentyfour_hours(fan: Device) -> None:
    """60 W at R$1/kWh equals R$0.06, R$0.48 and R$1.44 respectively."""
    assert cost_for_hours(fan, 1, 1) == pytest.approx((0.06, 0.06))
    assert cost_for_hours(fan, 8, 1) == pytest.approx((0.48, 0.48))
    assert cost_for_hours(fan, 24, 1) == pytest.approx((1.44, 1.44))


def test_shower_5500_watts_quarter_hour(fan: Device) -> None:
    """A 5.5 kW shower for 15 minutes draws 1.375 kWh."""
    shower = Device(fan.id, "Chuveiro", "Banheiro", 5500)
    assert cost_for_hours(shower, 0.25, 0.92) == pytest.approx((1.375, 1.265))


def test_illustrative_fan_schedule(fan: Device, fan_item: UsageItem) -> None:
    """An 8-hour daily fan averages 14.4 kWh per 30-day month."""
    result = estimate_item(fan, fan_item, 0.85)
    assert result.weekly_kwh == pytest.approx(3.36)
    assert result.monthly_kwh == pytest.approx(14.4)
    assert result.monthly_cost == pytest.approx(12.24)
    assert result.annual_kwh == pytest.approx(175.2)


def test_weekday_usage_is_scaled_to_30_day_month(fan: Device) -> None:
    """Five days weekly use is weighted using the explicit 30/7 approximation."""
    item = UsageItem(fan.id, 8, 5)
    result = estimate_item(fan, item, 1)
    assert result.weekly_kwh == pytest.approx(2.4)
    assert result.monthly_kwh == pytest.approx(2.4 * 30 / 7)
    assert result.annual_kwh == pytest.approx(2.4 * 365 / 7)


def test_quantity_and_average_load(fan: Device) -> None:
    """Three fans at half load consume 0.72 kWh over eight hours."""
    assert energy_kwh(fan.watts, 8, quantity=3, duty_cycle=0.5) == pytest.approx(0.72)
    result = estimate_item(fan, UsageItem(fan.id, 8, 7, 3, 0.5), 1)
    assert result.weekly_kwh == pytest.approx(3 * 0.5 * 3.36)


def test_standby_only_other_hours(fan: Device) -> None:
    """Standby runs in all non-active hours, even on days with zero scheduled use."""
    item = UsageItem(fan.id, 8, 5, include_standby=True)
    result = estimate_item(fan, item, 1)
    assert result.active_weekly_kwh == pytest.approx(2.4)
    assert result.standby_weekly_kwh == pytest.approx(2 * (168 - 40) / 1000)
    assert result.weekly_kwh == pytest.approx(2.656)


def test_full_week_active_has_no_standby(fan: Device) -> None:
    """A continuously active appliance cannot also be on standby."""
    result = estimate_item(fan, UsageItem(fan.id, 24, 7, include_standby=True), 1)
    assert result.standby_weekly_kwh == 0
    assert result.weekly_kwh == pytest.approx(60 * 168 / 1000)


def test_zero_active_load_with_standby(fan: Device) -> None:
    """An inactive plugged-in device can still consume standby energy."""
    result = estimate_item(fan, UsageItem(fan.id, 0, 1, include_standby=True), 1)
    assert result.weekly_kwh == pytest.approx(2 * 168 / 1000)


def test_scenario_sum_and_missing_devices(fan: Device, fan_scenario: Scenario) -> None:
    """Scenario aggregation fails explicitly when a saved device was removed."""
    estimates = estimate_scenario(fan_scenario, [fan], 0.85)
    assert totals(estimates)["monthly_cost"] == pytest.approx(12.24)
    with pytest.raises(ValueError, match="inexistente"):
        estimate_scenario(fan_scenario, [], 0.85)


def test_device_mismatch_is_rejected(fan: Device) -> None:
    """Direct estimates refuse a usage item belonging to a different device."""
    wrong = UsageItem("00000000-0000-4000-8000-000000000003", 1)
    with pytest.raises(ValueError, match="não corresponde"):
        estimate_item(fan, wrong, 1)


@pytest.mark.parametrize("bad", [-1, math.inf, math.nan, "100", True])
def test_bad_power_rejected(bad: object) -> None:
    """Wattage calculations reject invalid nonfinite and nonnumeric input."""
    with pytest.raises(ValueError):
        energy_kwh(bad, 8)  # type: ignore[arg-type]


@pytest.mark.parametrize("hours", [-1, math.inf, math.nan])
def test_bad_hours_rejected(hours: float) -> None:
    """A duration cannot be negative or unbounded."""
    with pytest.raises(ValueError):
        energy_kwh(60, hours)


def test_bad_quantity_and_load_rejected(fan: Device) -> None:
    """Quantity must be integral and duty must be a fraction in [0,1]."""
    for quantity in (0, 1.5, 1001):
        with pytest.raises(ValueError):
            cost_for_hours(fan, 8, 1, quantity=quantity)  # type: ignore[arg-type]
    for duty in (-0.01, 1.01):
        with pytest.raises(ValueError):
            cost_for_hours(fan, 8, 1, duty_cycle=duty)


def test_formatting() -> None:
    """Presentation uses Brazilian money and decimal separators."""
    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_number(1234.5678, 3) == "1.234,568"


def test_minutes_to_hours_for_shower() -> None:
    """Ten minutes must be preserved as exactly one-sixth of an hour."""
    assert hours_from_duration(10, "minutes") == pytest.approx(1 / 6)
    assert hours_from_duration(0.25, "hours") == pytest.approx(0.25)
    with pytest.raises(ValueError):
        hours_from_duration(1441, "minutes")
    with pytest.raises(ValueError):
        hours_from_duration(1, "seconds")
