"""Build a minimal, deterministic, privacy-safe GitHub Pages artifact.

No personal data, demo backups, .env files, tests or local dependency files are shipped.
The app runs with Stlite in-browser; Python source files are fetched from Pages.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "pages"
STATIC_FILES = ("index.html", "pages.css", "boot.js", "appearance.js", "favicon.svg")
PACKAGES = (ROOT / "src" / "energy_estimator",)
BUILD_MARKER = ".eue-github-pages-build"


def source_files() -> dict[str, Path]:
    """Only source modules needed at runtime (no user data, secrets or test files)."""
    results = {"app.py": ROOT / "app.py"}
    for package in PACKAGES:
        for path in sorted(package.glob("*.py")):
            results[path.relative_to(ROOT).as_posix()] = path
    return results


def pages_theme_stylesheet() -> str:
    """Derive the Pages stylesheet from the existing Python theme (stdlib only).

    This avoids a second, outdated CSS copy: the Stlite host page owns the
    stylesheet and changes the single data-eue-theme attribute on the root.
    """
    path = ROOT / "src" / "energy_estimator" / "ui_theme.py"
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    source = {}
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"_THEME_PALETTE_CSS", "_THEME_RULES"}:
                    source[target.id] = ast.literal_eval(node.value)
    if len(source) != 2:
        raise ValueError("Não foi possível localizar a folha de estilos do aplicativo.")
    old = ':root:has(#eue-active-theme[data-theme="dark"])'
    if source["_THEME_PALETTE_CSS"].count(old) != 1:
        raise ValueError("O seletor do tema escuro mudou; revise o gerador de Pages.")
    palette = source["_THEME_PALETTE_CSS"].replace(old, ':root[data-eue-theme="dark"]')
    return "/* Derived from ui_theme.py; do not edit the generated file. */\n" + palette + source["_THEME_RULES"] + "\n"


def build(output: Path) -> list[str]:
    """Recreate output strictly from allowlisted sources, never from the data dir."""
    output = output.resolve()
    if output == ROOT or output in ROOT.parents or (ROOT in output.parents and output != ROOT / "dist"):
        raise ValueError("O destino não pode ser o repositório nem uma pasta de fontes.")
    if output.exists():
        # Refuse to remove an unrelated directory, even if --output was mistyped.
        if any(output.iterdir()) and not (output / BUILD_MARKER).is_file():
            raise ValueError(f"Recusando substituir uma pasta não gerada por este script: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / BUILD_MARKER).write_text("Energy Usage Estimator Pages build\n", encoding="utf-8")
    for name in STATIC_FILES:
        shutil.copy2(SITE / name, output / name)
    (output / "app-theme.css").write_text(pages_theme_stylesheet(), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", output / "LICENSE")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    sources = source_files()
    for name, src in sources.items():
        if not src.is_file():
            raise FileNotFoundError(src)
        dest = output / "python" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    manifest = sorted(sources)
    (output / "files-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist", help="Pasta a publicar no Pages")
    args = parser.parse_args()
    paths = build(args.output)
    print(f"GitHub Pages: {len(paths)} módulos Python, {len(STATIC_FILES)} recursos estáticos -> {args.output}")


if __name__ == "__main__":
    main()
