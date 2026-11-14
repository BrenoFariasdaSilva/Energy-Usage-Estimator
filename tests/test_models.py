"""Domain invariants and JSON model round-trip tests."""

from __future__ import annotations

import math

import pytest

from energy_estimator.models import Device, Scenario, Tariff, UsageItem


def test_tariff_direct_and_bill() -> None:
    """Direct and bill modes return their documented per-kWh rates."""
    assert Tariff(direct_rate=0.85).rate == pytest.approx(0.85)
    assert Tariff("bill", 0.85, 275, 250).rate == pytest.approx(1.1)
    assert Tariff("bill", 0.85, 0, 250).rate == 0


def test_tariff_invalid_modes_and_zero_denominator() -> None:
    """Invalid billing inputs never silently produce an infinite rate."""
    with pytest.raises(ValueError):
        Tariff("incorrect")
    with pytest.raises(ValueError):
        Tariff("bill", 0.85, 123, 0)
    with pytest.raises(ValueError):
        Tariff("bill", 0.85, 123, math.nan)


def test_model_serialization_roundtrip(fan: Device, fan_scenario: Scenario) -> None:
    """Every saved domain object round-trips without losing power or schedule."""
    assert Device.from_dict(fan.to_dict()) == fan
    assert Scenario.from_dict(fan_scenario.to_dict()) == fan_scenario
    assert Tariff.from_dict(Tariff().to_dict()) == Tariff()
