"""Static artifact safety and storage selection (stdlib-only for CI bootstrap)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from energy_estimator import storage  # noqa: E402

spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
assert spec and spec.loader
build_pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_pages)


class GitHubPagesBuildTests(unittest.TestCase):
    def test_page_artifact_has_only_allowlisted_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "site"
            filenames = build_pages.build(output)
            self.assertEqual(filenames, json.loads((output / "files-manifest.json").read_text()))
            self.assertIn("app.py", filenames)
            self.assertIn("src/energy_estimator/bill_import.py", filenames)
            self.assertIn("src/energy_estimator/ui_theme.py", filenames)
            expected = {".nojekyll", "LICENSE", build_pages.BUILD_MARKER, "files-manifest.json", "app-theme.css", *build_pages.STATIC_FILES}
            expected.update("python/" + name for name in filenames)
            actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(expected, actual)
            for forbidden in ("data/settings.json", ".env", "README.md", "examples/backup-demo.json",
                              "requirements.txt", "tests/test_calculations.py", "PrimeiraViaCopel.pdf"):
                self.assertFalse((output / forbidden).exists(), forbidden)
            self.assertEqual((ROOT / "app.py").read_bytes(), (output / "python" / "app.py").read_bytes())
            self.assertEqual((ROOT / "src/energy_estimator/ui_theme.py").read_bytes(),
                             (output / "python/src/energy_estimator/ui_theme.py").read_bytes())

    def test_build_is_reproducible_and_does_not_publish_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "site"
            build_pages.build(output)
            first = {p.relative_to(output).as_posix(): p.read_bytes()
                     for p in output.rglob("*") if p.is_file()}
            build_pages.build(output)
            second = {p.relative_to(output).as_posix(): p.read_bytes()
                      for p in output.rglob("*") if p.is_file()}
            self.assertEqual(first, second)

    def test_build_refuses_to_delete_unrelated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "important"
            output.mkdir()
            sentinel = output / "private.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_pages.build(output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            with self.assertRaises(ValueError):
                build_pages.build(ROOT)
            with self.assertRaises(ValueError):
                build_pages.build(ROOT / "pages")

    def test_default_server_and_browser_storage_are_distinct(self) -> None:
        project = ROOT
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(storage, "is_browser_runtime", return_value=False):
            self.assertEqual(storage.data_directory(project), project / "data")
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(storage, "is_browser_runtime", return_value=True):
            self.assertEqual(storage.data_directory(project), Path("/mnt/energy-usage-estimator"))
        with mock.patch.dict(os.environ, {"ENERGY_ESTIMATOR_DATA_DIR": "/tmp/my-eue"}), mock.patch.object(
            storage, "is_browser_runtime", return_value=True
        ):
            self.assertEqual(storage.data_directory(project), Path("/tmp/my-eue"))

    def test_native_fsync_is_kept_and_browser_safely_flushes(self) -> None:
        class Handle:
            def __init__(self):
                self.flushed = 0
            def flush(self):
                self.flushed += 1
            def fileno(self):
                return 14
        handle = Handle()
        with mock.patch.object(storage, "is_browser_runtime", return_value=True), mock.patch.object(
            storage.os, "fsync"
        ) as fsync:
            storage.sync_local_file(handle)
            fsync.assert_not_called()
        self.assertEqual(handle.flushed, 1)
        with mock.patch.object(storage, "is_browser_runtime", return_value=False), mock.patch.object(
            storage.os, "fsync"
        ) as fsync:
            storage.sync_local_file(handle)
            fsync.assert_called_once_with(14)
        self.assertEqual(handle.flushed, 2)

    def test_pages_runtime_has_correct_baked_in_dependencies(self) -> None:
        html = (ROOT / "pages/index.html").read_text(encoding="utf-8")
        js = (ROOT / "pages/boot.js").read_text(encoding="utf-8")
        self.assertIn("@stlite/browser@1.11.0", html)
        self.assertIn('href="./app-theme.css"', html)
        self.assertIn("'theme.base': 'light'", js)
        self.assertIn("startAppearanceSync", js)
        css = build_pages.pages_theme_stylesheet()
        self.assertIn(':root[data-eue-theme="dark"]', css)
        self.assertNotIn(':root:has(#eue-active-theme', css)
        self.assertIn('[data-testid="stSidebar"]', css)
        self.assertIn("STLite_VERSION = '1.11.0'", js)
        for key in ("idbfsMountpoints", "stliteOptions", "pandas", "plotly", "pypdf", "files-manifest.json"):
            self.assertIn(key, js)
        self.assertNotIn("localStorage.clear", js)


if __name__ == "__main__":
    unittest.main()
