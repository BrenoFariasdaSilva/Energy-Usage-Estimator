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


def main(argv: list[str] | None = None) -> int:
    """Dispatch installation, local web dashboard or automated test suite."""
    parser = argparse.ArgumentParser(description="Instalação e execução do Energy Usage Estimator")
    parser.add_argument("action", choices=("run", "install", "test", "diagnostics"), nargs="?", default="run")
    args = parser.parse_args(argv)
    try:
        python = install_if_needed(development=args.action == "test")
        if args.action == "install":
            print("Instalação concluída.")
            return 0
        if args.action == "run":
            command = [str(python), "-m", "streamlit", "run", "app.py", "--server.address=127.0.0.1"]
        elif args.action == "test":
            command = [str(python), "-m", "pytest", "-q"]
        else:
            command = [str(python), "main.py", "diagnostics"]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        print("Verifique Python, acesso à internet para instalar pacotes e permissões de escrita.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
