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


def estimate_item(device: Device, item: UsageItem, rate: float) -> UsageEstimate:
    """Estimate a device's schedule, optionally including 24/7 standby load."""
    if device.id != item.device_id:
        raise ValueError("O aparelho não corresponde ao item do cenário.")
    _number(rate, "Tarifa (R$/kWh)", maximum=1000)
    active_hours = item.hours_per_day * item.days_per_week
    active_kwh = energy_kwh(device.watts, active_hours, quantity=item.quantity, duty_cycle=item.duty_cycle)
    standby_hours = HOURS_PER_WEEK - active_hours if item.include_standby else 0
    standby_kwh = energy_kwh(device.standby_watts, standby_hours, quantity=item.quantity)
    week = active_kwh + standby_kwh
    month = week * DAYS_PER_MONTH / 7
    year = week * DAYS_PER_YEAR / 7
    return UsageEstimate(
        device_id=device.id,
        device_name=device.name,
        weekly_kwh=week,
        monthly_kwh=month,
        annual_kwh=year,
        weekly_cost=week * rate,
        monthly_cost=month * rate,
        annual_cost=year * rate,
        active_weekly_kwh=active_kwh,
        standby_weekly_kwh=standby_kwh,
    )


def estimate_scenario(scenario: Scenario, devices: list[Device], rate: float) -> list[UsageEstimate]:
    """Return per-item estimates, with missing-device references rejected."""
    device_by_id = {device.id: device for device in devices}
    rows: list[UsageEstimate] = []
    for item in scenario.items:
        if item.device_id not in device_by_id:
            raise ValueError(f"Cenário '{scenario.name}' referencia aparelho inexistente: {item.device_id}.")
        rows.append(estimate_item(device_by_id[item.device_id], item, rate))
    return rows


def totals(estimates: list[UsageEstimate]) -> dict[str, float]:
    """Sum energy and cost at each time horizon."""
    keys = ("weekly_kwh", "monthly_kwh", "annual_kwh", "weekly_cost", "monthly_cost", "annual_cost")
    return {key: sum(getattr(estimate, key) for estimate in estimates) for key in keys}


def format_brl(amount: float) -> str:
    """Format BRL monetary amounts independently of system locale."""
    _number(amount, "Valor monetário", maximum=1_000_000_000_000_000_000)
    return "R$ " + f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_number(amount: float, decimals: int = 2) -> str:
    """Format decimal quantities with Brazilian grouping and separators."""
    return f"{amount:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
