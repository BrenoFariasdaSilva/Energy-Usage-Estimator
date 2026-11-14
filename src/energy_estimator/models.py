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
