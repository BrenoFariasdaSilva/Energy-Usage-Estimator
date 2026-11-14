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


def test_wrong_schema_never_silently_reset(tmp_path: Path) -> None:
    """Unknown schema versions are rejected instead of silently erased."""
    (tmp_path / "settings.json").write_text('{"schema_version": 2, "tariff": {}}')
    with pytest.raises(StorageError, match="incompatível"):
        JsonStore(tmp_path).load_tariff()


def test_export_import_with_previous_backup(tmp_path: Path, fan: Device, fan_scenario: Scenario) -> None:
    """A full JSON export restores every collection and leaves an automatic safety copy."""
    original = JsonStore(tmp_path / "original")
    original.upsert_device(fan)
    original.upsert_scenario(fan_scenario)
    original.save_tariff(Tariff("bill", 0.85, 300, 250))
    exported = original.backup_bytes()
    assert b"energy-usage-estimator" in exported
    restored = JsonStore(tmp_path / "restored")
    restored.save_tariff(Tariff(direct_rate=0.4))
    previous = restored.restore_backup(exported)
    assert previous.exists()
    assert json.loads(previous.read_bytes())["tariff"]["direct_rate"] == 0.4
    assert restored.load_all() == original.load_all()


def test_import_invalid_backup_preserves_existing_state(tmp_path: Path, fan: Device) -> None:
    """Failure to validate foreign keys cannot damage preexisting user records."""
    store = JsonStore(tmp_path)
    store.upsert_device(fan)
    snapshot = store.backup_bytes()
    malformed = json.loads(snapshot)
    malformed["scenarios"] = [
        Scenario(new_id(), "Órfão", items=(UsageItem(new_id(), 1),)).to_dict()
    ]
    with pytest.raises(ValueError, match="inexistente"):
        store.restore_backup(json.dumps(malformed).encode())
    assert store.backup_bytes() != b""  # Export timestamps are dynamic; compare content instead.
    assert store.load_devices() == [fan]
    assert not (tmp_path / "backups").exists()


def test_oversized_import_and_foreign_backup_rejected(tmp_path: Path) -> None:
    """Unexpected documents and giant uploads are rejected before any write."""
    store = JsonStore(tmp_path)
    with pytest.raises(ValueError, match="5 MB"):
        store.restore_backup(b"x" * (5 * 1024 * 1024 + 1))
    invalid = {"schema_version": 1, "app": "other", "devices": [], "scenarios": [], "tariff": Tariff().to_dict()}
    with pytest.raises(ValueError, match="não é um backup"):
        store.restore_backup(json.dumps(invalid).encode())
    assert list(tmp_path.iterdir()) == []


def test_import_rollback_if_second_write_fails(tmp_path: Path, fan: Device, monkeypatch) -> None:
    """Write errors during import restore the previous validated records."""
    original = JsonStore(tmp_path / "source")
    original.upsert_device(fan)
    exported = original.backup_bytes()
    store = JsonStore(tmp_path / "destination")
    store.save_tariff(Tariff(direct_rate=0.9))
    real_write = store._write
    failed = [False]

    def fail_once(name, document):
        if name == "scenarios" and not failed[0]:
            failed[0] = True
            raise StorageError("Simulated disk failure")
        return real_write(name, document)

    monkeypatch.setattr(store, "_write", fail_once)
    with pytest.raises(StorageError, match="Simulated"):
        store.restore_backup(exported)
    assert store.load_all() == ([], [], Tariff(direct_rate=0.9))
    assert list((tmp_path / "destination" / "backups").glob("*.json"))


def test_env_override(tmp_path: Path, monkeypatch) -> None:
    """Custom directory is explicit and does not change project files."""
    monkeypatch.setenv("ENERGY_ESTIMATOR_DATA_DIR", str(tmp_path / "custom"))
    assert data_directory(tmp_path) == (tmp_path / "custom").resolve()
    monkeypatch.delenv("ENERGY_ESTIMATOR_DATA_DIR")
    assert data_directory(tmp_path) == tmp_path / "data"


def test_catalog_adds_only_missing_names(fan: Device) -> None:
    """Catalog starter examples do not overwrite existing user wattages."""
    examples = example_devices([fan])
    assert len(examples) == len(EXAMPLES) - 1
    assert all(item.id != fan.id for item in examples)
    assert "Ventilador" not in [item.name for item in examples]
