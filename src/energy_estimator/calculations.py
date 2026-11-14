"""Pure estimation formulas; no Streamlit, filesystem, or network dependency."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Device, Scenario, UsageItem, _number

DAYS_PER_MONTH = 30
DAYS_PER_YEAR = 365
HOURS_PER_WEEK = 24 * 7


@dataclass(frozen=True, slots=True)
class UsageEstimate:
    """Estimated energy and money at weekly, 30-day, and 365-day horizons."""

    device_id: str
    device_name: str
    weekly_kwh: float
    monthly_kwh: float
    annual_kwh: float
    weekly_cost: float
    monthly_cost: float
    annual_cost: float
    active_weekly_kwh: float
    standby_weekly_kwh: float


def hours_from_duration(value: float, unit: str = "hours") -> float:
    """Convert a human-entered duration from hours or minutes to hours (0–24)."""
    if unit == "hours":
        return _number(value, "Horas por dia", maximum=24)
    if unit == "minutes":
        return _number(value, "Minutos por dia", maximum=1440) / 60
    raise ValueError("Unidade de tempo desconhecida.")


def energy_kwh(watts: float, hours: float, *, quantity: int = 1, duty_cycle: float = 1.0) -> float:
    """Compute active energy for a duration, using a mean load fraction."""
    _number(watts, "Potência (W)")
    _number(hours, "Horas", maximum=1_000_000)
    _number(quantity, "Quantidade", minimum=1, maximum=1000)
    if int(quantity) != quantity:
        raise ValueError("Quantidade precisa ser um número inteiro.")
    _number(duty_cycle, "Ciclo", maximum=1)
    return watts * hours * quantity * duty_cycle / 1000


def cost_for_hours(device: Device, hours: float, rate: float, *, quantity: int = 1, duty_cycle: float = 1.0) -> tuple[float, float]:
    """Return kWh and cost for continuous scheduled hours, excluding standby."""
    _number(rate, "Tarifa (R$/kWh)", maximum=1000)
    kwh = energy_kwh(device.watts, hours, quantity=quantity, duty_cycle=duty_cycle)
    return kwh, kwh * rate
