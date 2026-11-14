"""Shared test fixtures for the energy estimator."""

from __future__ import annotations

import pytest

from energy_estimator.models import Device, Scenario, UsageItem


@pytest.fixture
def fan() -> Device:
    """A representative 60 W appliance with 2 W standby power."""
    return Device("00000000-0000-4000-8000-000000000001", "Ventilador", "Climatização", 60, 2)


@pytest.fixture
def fan_item(fan: Device) -> UsageItem:
    """A normal-use weekly schedule for the fan."""
    return UsageItem(fan.id, 8, 7)


@pytest.fixture
def fan_scenario(fan_item: UsageItem) -> Scenario:
    """A scenario referencing the representative appliance."""
    return Scenario("00000000-0000-4000-8000-000000000002", "Casa", "", (fan_item,))
