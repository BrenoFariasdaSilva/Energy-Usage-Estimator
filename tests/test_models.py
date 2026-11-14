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


def test_device_missing_required_fields_rejected() -> None:
    """Required device fields are not silently filled from missing JSON keys."""
    with pytest.raises(TypeError):
        Device.from_dict({"name": "Incompleto"})


@pytest.mark.parametrize("bad_name", ["", " ", "x" * 121, None])
def test_device_bad_names_rejected(fan: Device, bad_name: object) -> None:
    """Device names must be usable and have reasonable length."""
    with pytest.raises(ValueError):
        Device(fan.id, bad_name, "Cozinha", 40)  # type: ignore[arg-type]


def test_device_negative_standby_rejected(fan: Device) -> None:
    """Standby watts must be nonnegative."""
    with pytest.raises(ValueError):
        Device(fan.id, "A", "B", 100, -1)


def test_usage_bounds(fan: Device) -> None:
    """Hours/day, days/week, quantity and load fractions enforce valid ranges."""
    for arguments in ({"hours_per_day": 24.01}, {"days_per_week": 0}, {"days_per_week": 8},
                      {"quantity": 0}, {"duty_cycle": 1.1}, {"include_standby": 1}):
        values = {"device_id": fan.id, "hours_per_day": 1, **arguments}
        with pytest.raises(ValueError):
            UsageItem(**values)


def test_scenario_rejects_duplicate_devices(fan: Device) -> None:
    """Each saved scenario contains at most one schedule per device."""
    usage = UsageItem(fan.id, 2)
    with pytest.raises(ValueError, match="uma vez"):
        Scenario("00000000-0000-4000-8000-000000000005", "Duplicado", items=(usage, usage))


def test_scenario_rejects_wrong_json_shape() -> None:
    """Scenario items are a list in persisted JSON, never a string or mapping."""
    with pytest.raises(ValueError):
        Scenario.from_dict({"id": "x", "name": "A", "items": "invalid"})


def test_trim_normalization_before_duplicate_checks(fan: Device) -> None:
    """Space-padded user names are canonicalized before persistence and comparison."""
    padded = Device(fan.id, "  Ventilador   ", "  Climatização  ", 60, notes="  teste  ")
    assert padded.name == "Ventilador"
    assert padded.category == "Climatização"
    assert padded.notes == "teste"
    scenario = Scenario("00000000-0000-4000-8000-000000000007", "  Casa  ")
    assert scenario.name == "Casa"
