"""Illustrative catalog; actual rated and average power vary by model."""

from __future__ import annotations

from .models import Device, new_id

# Examples are not laboratory measurements or guaranteed device consumption.
EXAMPLES: tuple[tuple[str, str, float, float], ...] = (
    ("Ventilador", "Climatização", 60, 0),
    ("Chuveiro elétrico", "Banheiro", 5500, 0),
    ("PC desktop", "Informática", 300, 2),
    ("Notebook", "Informática", 65, 1),
    ("Monitor", "Informática", 30, 0.5),
    ("Televisão LED", "Entretenimento", 100, 1),
    ("Ar-condicionado", "Climatização", 1200, 2),
    ("Geladeira", "Cozinha", 150, 0),
    ("Micro-ondas", "Cozinha", 1400, 1),
    ("Roteador Wi-Fi", "Informática", 12, 0),
    ("Lâmpada LED", "Iluminação", 10, 0),
    ("Máquina de lavar", "Lavanderia", 500, 0),
    ("Ferro de passar", "Lavanderia", 1200, 0),
    ("Secador de cabelo", "Banheiro", 1800, 0),
    ("Console de videogame", "Entretenimento", 200, 1),
)


def example_devices(existing: list[Device]) -> list[Device]:
    """Create only catalog devices not already present by normalized name."""
    normalized = {item.name.casefold() for item in existing}
    return [
        Device(new_id(), name, category, watts, standby,
               "Valor ilustrativo; substitua pela potência medida ou indicada no aparelho.")
        for name, category, watts, standby in EXAMPLES if name.casefold() not in normalized
    ]
