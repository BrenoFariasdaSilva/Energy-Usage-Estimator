"""Run the CLI without a Streamlit dependency or internet access."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the shipped main.py entry point in a real Python subprocess."""
    return subprocess.run([sys.executable, str(ROOT / "main.py"), *args], capture_output=True, text=True, check=False)


def test_cli_60_watt_8h() -> None:
    """CLI renders a precise energy/currency estimate from explicit inputs."""
    result = invoke("estimate", "--watts", "60", "--hours", "8", "--rate", "0.85")
    assert result.returncode == 0, result.stderr
    assert "0,4800 kWh" in result.stdout
    assert "R$ 0,41" in result.stdout


def test_cli_invalid_rate_fails() -> None:
    """A negative rate is an explicit nonzero CLI error."""
    result = invoke("estimate", "--watts", "60", "--hours", "8", "--rate", "-1")
    assert result.returncode == 1
    assert "Erro" in result.stderr


def test_cli_diagnostics_with_empty_storage(tmp_path: Path, monkeypatch) -> None:
    """The diagnostics command does not require Streamlit to be imported."""
    monkeypatch.setenv("ENERGY_ESTIMATOR_DATA_DIR", str(tmp_path / "testdata"))
    from energy_estimator.storage import JsonStore

    assert JsonStore(tmp_path / "testdata").load_devices() == []
    result = invoke("diagnostics")
    assert result.returncode == 0, result.stderr
    assert "Aparelhos" in result.stdout
