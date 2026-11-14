"""Local persistence safety, corruption, backups, constraints and import tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from energy_estimator.models import Device, Scenario, Tariff, UsageItem, new_id
from energy_estimator.presets import EXAMPLES, example_devices
from energy_estimator.storage import JsonStore, StorageError, data_directory


def test_default_store_is_non_destructive(tmp_path: Path) -> None:
    """A fresh launch must not write files before the first user action."""
    store = JsonStore(tmp_path / "data")
    assert store.load_all() == ([], [], Tariff())
    assert not store.directory.exists()


def test_roundtrip_devices_scenarios_tariff(tmp_path: Path, fan: Device, fan_scenario: Scenario) -> None:
    """Saving all three collections survives a new store instance."""
    store = JsonStore(tmp_path)
    store.upsert_device(fan)
    store.upsert_scenario(fan_scenario)
    store.save_tariff(Tariff("bill", 0.8, 200, 250))
    assert JsonStore(tmp_path).load_all() == ([fan], [fan_scenario], Tariff("bill", 0.8, 200, 250))
    assert json.loads((tmp_path / "devices.json").read_text())["schema_version"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_upserts_edit_in_place(tmp_path: Path, fan: Device) -> None:
    """Editing a device by ID never creates an accidental duplicate."""
    store = JsonStore(tmp_path)
    store.upsert_device(fan)
    edited = Device(fan.id, fan.name, fan.category, 120)
    store.upsert_device(edited)
    assert store.load_devices() == [edited]


def test_duplicate_names_rejected(tmp_path: Path, fan: Device) -> None:
    """Equivalent names with different identifiers cannot coexist."""
    store = JsonStore(tmp_path)
    store.upsert_device(fan)
    with pytest.raises(ValueError, match="Já existe"):
        store.upsert_device(Device(new_id(), "VENTILADOR", "C", 120))


def test_delete_device_referenced_is_blocked(tmp_path: Path, fan: Device, fan_scenario: Scenario) -> None:
    """An appliance cannot be deleted while any saved schedule references it."""
    store = JsonStore(tmp_path)
    store.upsert_device(fan)
    store.upsert_scenario(fan_scenario)
    with pytest.raises(ValueError, match="Remova"):
        store.delete_device(fan.id)
    assert len(store.load_devices()) == 1
    assert store.delete_scenario(fan_scenario.id)
    assert store.delete_device(fan.id)
    assert store.load_devices() == []


def test_missing_referenced_device_rejected(tmp_path: Path, fan_scenario: Scenario) -> None:
    """Scenarios referring to nonexistent devices must not be stored."""
    with pytest.raises(ValueError, match="inexistente"):
        JsonStore(tmp_path).upsert_scenario(fan_scenario)


def test_corrupted_json_never_overwritten(tmp_path: Path, fan: Device) -> None:
    """A malformed user JSON file remains untouched after read and save attempts."""
    path = tmp_path / "devices.json"
    path.write_text("{ invalid", encoding="utf-8")
    store = JsonStore(tmp_path)
    with pytest.raises(StorageError, match="JSON inválido"):
        store.load_devices()
    with pytest.raises(StorageError):
        store.upsert_device(fan)
    assert path.read_text(encoding="utf-8") == "{ invalid"
