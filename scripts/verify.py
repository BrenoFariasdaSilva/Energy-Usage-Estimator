"""Run deterministic project checks without shell-specific syntax."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str], *, required: bool = True) -> bool:
    """Run one finite check and print a portable status line."""
    if shutil.which(command[0]) is None:
        print(f"{'FAIL' if required else 'SKIPPED'} {name}: executable unavailable: {command[0]}")
        return not required
    result = subprocess.run(command, cwd=ROOT, check=False)
    print(f"{'PASS' if result.returncode == 0 else 'FAIL'} {name}")
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Energy Usage Estimator verification checks")
    parser.add_argument("--browser", action="store_true", help="Require Playwright fixture checks")
    args = parser.parse_args(argv)
    python = sys.executable
    checks = [
        ("pytest", [python, "-m", "pytest", "-q"]),
        ("ruff", [python, "-m", "ruff", "check", "."]),
        ("compile", [python, "-m", "compileall", "-q", "app.py", "main.py", "src", "pages", "scripts"]),
        ("pages boot tests", ["node", "--test", "tests/test_pages_boot.mjs"]),
        ("pages boot syntax", ["node", "--check", "pages/boot.js"]),
        ("appearance syntax", ["node", "--check", "pages/appearance.js"]),
        ("pages build", [python, "scripts/build_pages.py", "--output", "dist"]),
        ("launcher diagnostics", [python, "scripts/launcher.py", "diagnostics"]),
        (
            "CLI estimate",
            [
                python,
                "main.py",
                "estimate",
                "--watts",
                "300",
                "--hours",
                "8",
                "--rate",
                "1.0",
                "--quantity",
                "1",
                "--load",
                "100",
            ],
        ),
    ]
    passed = all(run(name, command) for name, command in checks)
    has_playwright = importlib.util.find_spec("playwright") is not None
    if args.browser or has_playwright:
        passed = run("theme browser fixture", [python, "scripts/verify_theme_fixture.py"]) and passed
        passed = run("Pages browser fixture", [python, "scripts/verify_pages_appearance.py"]) and passed
    else:
        print("SKIPPED browser fixtures: install playwright and run with --browser")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
