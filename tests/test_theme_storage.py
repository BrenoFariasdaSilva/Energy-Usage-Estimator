"""Regression tests for on-disk theme preferences and explicit JSON checkpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from energy_estimator.models import Device, Scenario, Tariff, UsageItem, new_id
from energy_estimator.storage import JsonStore, StorageError
from energy_estimator.ui_theme import THEMES, style_chart, theme_css


def test_old_settings_without_theme_remain_supported(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_tariff(Tariff(direct_rate=0.87))
    assert store.load_theme() == "light"
    assert "appearance" not in json.loads((tmp_path / "settings.json").read_text())
    assert store.load_tariff().rate == 0.87


def test_theme_survives_tariff_change(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_tariff(Tariff(direct_rate=0.91))
    store.save_theme("dark")
    store.save_tariff(Tariff(direct_rate=1.17))
    assert store.load_theme() == "dark"
    assert store.load_tariff().rate == 1.17
    assert json.loads((tmp_path / "settings.json").read_text())["appearance"] == "dark"


def test_first_theme_selection_creates_settings_with_default_tariff(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_theme("dark")
    assert store.load_theme() == "dark"
    assert store.load_tariff().rate == 1.0
    assert not (tmp_path / "devices.json").exists()


@pytest.mark.parametrize("theme", ["dark", "light", "system", 123, "", None])
def test_invalid_theme_is_rejected_without_overwriting_settings(tmp_path: Path, theme) -> None:
    store = JsonStore(tmp_path)
    store.save_tariff(Tariff(direct_rate=1.23))
    original = (tmp_path / "settings.json").read_bytes()
    if theme not in ("dark", "light"):
        with pytest.raises(ValueError, match="Tema inválido"):
            store.save_theme(theme)
        assert (tmp_path / "settings.json").read_bytes() == original


def test_corrupted_theme_detected_before_backup_or_tariff_save(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_tariff(Tariff())
    raw = json.loads((tmp_path / "settings.json").read_text())
    raw["appearance"] = "PURPLE"
    (tmp_path / "settings.json").write_text(json.dumps(raw))
    with pytest.raises(StorageError, match="Tema inválido"):
        store.load_theme()
    with pytest.raises(StorageError, match="Tema inválido"):
        store.save_tariff(Tariff(direct_rate=3))
    assert json.loads((tmp_path / "settings.json").read_text())["appearance"] == "PURPLE"


def test_manual_save_creates_all_json_and_dated_backup(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    checkpoint = store.save_now()
    assert checkpoint.exists()
    assert checkpoint.parent == tmp_path / "backups"
    assert checkpoint.name.startswith("manual-")
    for name in ("devices", "scenarios", "settings"):
        assert (tmp_path / f"{name}.json").is_file()
    snapshot = json.loads(checkpoint.read_text())
    assert snapshot["app"] == "energy-usage-estimator"
    assert snapshot["tariff"]["direct_rate"] == 1.0
    assert snapshot["appearance"] == "light"
    assert snapshot["devices"] == []
    assert snapshot["scenarios"] == []
    assert (another := store.save_now()) != checkpoint
    assert checkpoint.read_bytes() and another.read_bytes()


def test_manual_backup_captures_confirmed_data_without_mutations(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    computer = Device(new_id(), "Computer", "IT", 320)
    scenario = Scenario(new_id(), "Weekly", items=(UsageItem(computer.id, 4),))
    store.upsert_device(computer)
    store.upsert_scenario(scenario)
    store.save_tariff(Tariff(direct_rate=1.026488))
    store.save_theme("dark")
    checkpoint = store.save_now()
    backup = json.loads(checkpoint.read_text())
    assert backup["devices"] == [computer.to_dict()]
    assert backup["scenarios"] == [scenario.to_dict()]
    assert backup["tariff"]["direct_rate"] == 1.026488
    assert backup["appearance"] == "dark"
    assert store.load_all() == ([computer], [scenario], Tariff(direct_rate=1.026488))


def test_export_and_restore_roundtrip_theme(tmp_path: Path) -> None:
    source = JsonStore(tmp_path / "source")
    source.save_theme("dark")
    source.save_tariff(Tariff(direct_rate=1.5))
    raw = source.backup_bytes()
    destination = JsonStore(tmp_path / "destination")
    destination.save_theme("light")
    destination.restore_backup(raw)
    assert destination.load_theme() == "dark"
    assert destination.load_tariff().rate == 1.5


def test_restore_legacy_backup_without_theme_uses_light(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_theme("dark")
    backup = json.loads(store.backup_bytes())
    del backup["appearance"]
    store.restore_backup(json.dumps(backup).encode("utf-8"))
    assert store.load_theme() == "light"


def test_restore_invalid_theme_never_changes_data(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_tariff(Tariff(direct_rate=1.2))
    store.save_theme("dark")
    source = json.loads(store.backup_bytes())
    source["appearance"] = "invalid"
    with pytest.raises(ValueError, match="Tema inválido"):
        store.restore_backup(json.dumps(source).encode("utf-8"))
    assert store.load_theme() == "dark"
    assert store.load_tariff().rate == 1.2
    assert not (tmp_path / "backups").exists()


def test_restore_partial_write_rolls_back_theme(tmp_path: Path, monkeypatch) -> None:
    store = JsonStore(tmp_path)
    store.save_theme("dark")
    store.save_tariff(Tariff(direct_rate=0.7))
    incoming = json.loads(store.backup_bytes())
    incoming["appearance"] = "light"
    incoming["tariff"]["direct_rate"] = 5.0
    orig = store._write
    failed = False

    def fail_once(name, document):
        nonlocal failed
        if name == "settings" and not failed:
            failed = True
            raise StorageError("Simulated write error")
        return orig(name, document)

    monkeypatch.setattr(store, "_write", fail_once)
    with pytest.raises(StorageError, match="Simulated"):
        store.restore_backup(json.dumps(incoming).encode("utf-8"))
    assert store.load_theme() == "dark"
    assert store.load_tariff().rate == 0.7
