"""Validated, dependency-free domain models for local energy estimates."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from uuid import UUID, uuid4


def new_id() -> str:
    """Return a random stable identifier; names are not used as identifiers."""
    return str(uuid4())


def _text(value: object, label: str, *, max_length: int = 120, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} deve ser texto.")
    value = value.strip()
    if (required and not value) or len(value) > max_length:
        raise ValueError(f"{label} deve ter entre {1 if required else 0} e {max_length} caracteres.")
    return value


def _number(value: object, label: str, *, minimum: float = 0, maximum: float = 1_000_000) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} precisa ser um número.")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label} deve estar entre {minimum:g} e {maximum:g}.")
    return result


def _integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} deve ser um inteiro entre {minimum} e {maximum}.")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} inválido.")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ValueError(f"{label} precisa ser um UUID.") from exc


@dataclass(frozen=True, slots=True)
class Device:
    """Reusable electrical appliance, with nominal power while active."""

    id: str
    name: str
    category: str
    watts: float
    standby_watts: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _id(self.id, "ID do aparelho"))
        object.__setattr__(self, "name", _text(self.name, "Nome"))
        object.__setattr__(self, "category", _text(self.category, "Categoria"))
        _number(self.watts, "Potência (W)", minimum=0.001, maximum=1_000_000)
        _number(self.standby_watts, "Potência em espera (W)")
        object.__setattr__(self, "notes", _text(self.notes, "Observações", max_length=500, required=False))

    @classmethod
    def from_dict(cls, data: object) -> Device:
        """Validate and parse one device from persisted JSON."""
        if not isinstance(data, dict):
            raise ValueError("Aparelho deve ser um objeto JSON.")
        return cls(**{key: data[key] for key in ("id", "name", "category", "watts", "standby_watts", "notes") if key in data})

    def to_dict(self) -> dict[str, object]:
        """Serialize the device into a JSON-compatible dictionary."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class UsageItem:
    """Usage schedule of one device inside a scenario."""

    device_id: str
    hours_per_day: float
    days_per_week: int = 7
    quantity: int = 1
    duty_cycle: float = 1.0
    include_standby: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_id", _id(self.device_id, "ID do aparelho"))
        _number(self.hours_per_day, "Horas de uso por dia", maximum=24)
        _integer(self.days_per_week, "Dias por semana", minimum=1, maximum=7)
        _integer(self.quantity, "Quantidade", minimum=1, maximum=1000)
        _number(self.duty_cycle, "Ciclo de funcionamento", maximum=1)
        if not isinstance(self.include_standby, bool):
            raise ValueError("Incluir consumo em espera deve ser verdadeiro ou falso.")

    @classmethod
    def from_dict(cls, data: object) -> UsageItem:
        """Validate and parse one usage schedule from JSON."""
        if not isinstance(data, dict):
            raise ValueError("Item do cenário deve ser um objeto JSON.")
        return cls(**{key: data[key] for key in (
            "device_id", "hours_per_day", "days_per_week", "quantity", "duty_cycle", "include_standby"
        ) if key in data})

    def to_dict(self) -> dict[str, object]:
        """Serialize a usage schedule."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Scenario:
    """Named collection of appliance schedules that can be saved and compared."""

    id: str
    name: str
    description: str = ""
    items: tuple[UsageItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _id(self.id, "ID do cenário"))
        object.__setattr__(self, "name", _text(self.name, "Nome do cenário"))
        object.__setattr__(self, "description", _text(self.description, "Descrição", max_length=500, required=False))
        if not isinstance(self.items, tuple) or not all(isinstance(item, UsageItem) for item in self.items):
            raise ValueError("Itens do cenário inválidos.")
        ids = [item.device_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Um aparelho só pode aparecer uma vez em cada cenário.")

    @classmethod
    def from_dict(cls, data: object) -> Scenario:
        """Validate and parse a complete scenario from JSON."""
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("Cenário ou lista de itens inválido.")
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            items=tuple(UsageItem.from_dict(item) for item in data["items"]),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize a complete scenario using JSON arrays for its usage items."""
        return {"id": self.id, "name": self.name, "description": self.description,
                "items": [item.to_dict() for item in self.items]}


@dataclass(frozen=True, slots=True)
class Tariff:
    """Local currency rate, entered directly or estimated from a whole bill."""

    mode: str = "direct"
    direct_rate: float = 1.0
    bill_amount: float = 0.0
    bill_kwh: float = 0.0
    source: str = "manual"
    bill_reference: str = ""

    def __post_init__(self) -> None:
        if self.mode not in ("direct", "bill"):
            raise ValueError("Modo de tarifa inválido.")
        if self.source not in ("manual", "copel_pdf"):
            raise ValueError("Origem da tarifa inválida.")
        if not isinstance(self.bill_reference, str) or (self.bill_reference and not re.fullmatch(r"(?:0[1-9]|1[0-2])/20\d{2}", self.bill_reference)):
            raise ValueError("Referência da fatura inválida.")
        _number(self.direct_rate, "Tarifa (R$/kWh)", maximum=1000)
        _number(self.bill_amount, "Valor da fatura (R$)", maximum=10_000_000)
        _number(self.bill_kwh, "Consumo na fatura (kWh)", maximum=10_000_000)
        if self.mode == "bill" and self.bill_kwh <= 0:
            raise ValueError("O consumo da fatura precisa ser maior do que zero.")
        if self.mode == "bill" and self.bill_amount / self.bill_kwh > 1000:
            raise ValueError("A tarifa efetiva calculada excede R$ 1.000/kWh. Confira os valores informados.")

    @property
    def rate(self) -> float:
        """Return effective cost for one kWh in the chosen billing mode."""
        return self.direct_rate if self.mode == "direct" else self.bill_amount / self.bill_kwh

    @classmethod
    def from_dict(cls, data: object) -> Tariff:
        """Load a persisted tariff, validating all values."""
        if not isinstance(data, dict):
            raise ValueError("A configuração da tarifa deve ser um objeto JSON.")
        return cls(**{key: data[key] for key in ("mode", "direct_rate", "bill_amount", "bill_kwh", "source", "bill_reference") if key in data})

    def to_dict(self) -> dict[str, object]:
        """Serialize the tariff configuration."""
        return asdict(self)
