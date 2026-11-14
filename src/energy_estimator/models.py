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
