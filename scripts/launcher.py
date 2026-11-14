"""Cross-platform one-command bootstrap and Streamlit launcher (Python stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".energy-estimator-requirements.sha256"


def venv_python() -> Path:
    """Return Python executable inside the repository virtual environment."""
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def checked_run(command: list[str], *, label: str) -> None:
    """Execute a dependency action and clearly propagate errors."""
    print(f"{label}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def install_if_needed(*, development: bool = False) -> Path:
    """Bootstrap a virtualenv, installing dependencies only when they change."""
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 ou mais recente é necessário. Atualize o Python e tente novamente.")
    extra = ROOT / "requirements-dev.txt"
    contents = REQUIREMENTS.read_bytes() + (extra.read_bytes() if development else b"")
    fingerprint = hashlib.sha256(contents + sys.version.encode()).hexdigest()
    python = venv_python()
    if not python.is_file():
        print("Criando o ambiente virtual .venv...", flush=True)
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not STAMP.exists() or STAMP.read_text(encoding="utf-8").strip() != fingerprint:
        command = [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
        if development:
            command.extend(["-r", str(extra)])
        checked_run(command, label="Instalando dependências")
        STAMP.write_text(fingerprint, encoding="utf-8")
    return python
