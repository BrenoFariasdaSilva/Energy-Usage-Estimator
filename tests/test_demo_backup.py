"""Demo backup is importable and produces genuinely different usage scenarios."""

from __future__ import annotations

from pathlib import Path

from energy_estimator.calculations import estimate_scenario, totals
from energy_estimator.storage import JsonStore


def test_example_backup_import_and_recompute(tmp_path: Path) -> None:
    """The provided reusable example is a valid, nontrivial two-scenario import."""
    demo = Path(__file__).resolve().parents[1] / "examples" / "backup-demo.json"
    store = JsonStore(tmp_path)
    store.restore_backup(demo.read_bytes())
    devices, scenarios, tariff = store.load_all()
    assert len(devices) == 4
    assert len(scenarios) == 2
    assert tariff.rate == 1.0
    before = totals(estimate_scenario(scenarios[0], devices, tariff.rate))["monthly_cost"]
    after = totals(estimate_scenario(scenarios[1], devices, tariff.rate))["monthly_cost"]
    assert 0 < after < before
