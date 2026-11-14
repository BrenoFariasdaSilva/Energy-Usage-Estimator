"""Streamlit interface smoke tests via a small widget stub, without installing Streamlit.

These tests validate routing and import/save interactions, NOT browser rendering.
"""

from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

import pytest

from energy_estimator.models import Tariff
from energy_estimator.storage import JsonStore

ROOT = Path(__file__).resolve().parents[1]


class RerunRequested(RuntimeError):
    """Emulate Streamlit rerun after a successful import."""


class UploadedBill:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def getvalue(self) -> bytes:
        return self.content


class FakeStreamlit(types.ModuleType):
    """Conservative API stub for routing and the specific bill upload interaction."""

    def __init__(self, page: str = "Início", upload: bytes | None = None, apply: bool = False,
                 theme: str | None = None, manual: bool = False):
        super().__init__("streamlit")
        self.sidebar = self
        self.session_state: dict[str, object] = {}
        self.page = page
        self.upload = upload
        self.apply = apply
        self.theme = theme
        self.manual = manual
        self.messages: list[tuple[str, str]] = []
        self.metrics: list[tuple[str, object]] = []
        self.html_calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def set_page_config(self, **_kwargs):
        pass

    def markdown(self, *_args, **_kwargs):
        pass

    def html(self, html_content, **_kwargs):
        self.html_calls.append(str(html_content))

    def title(self, *_args, **_kwargs):
        pass

    def caption(self, value, **_kwargs):
        self.messages.append(("caption", str(value)))

    def info(self, value, **_kwargs):
        self.messages.append(("info", str(value)))

    def error(self, value, **_kwargs):
        self.messages.append(("error", str(value)))

    def warning(self, value, **_kwargs):
        self.messages.append(("warning", str(value)))

    def success(self, value, **_kwargs):
        self.messages.append(("success", str(value)))

    def metric(self, label, value, **_kwargs):
        self.metrics.append((label, value))

    def expander(self, *_args, **_kwargs):
        return self

    def form(self, *_args, **_kwargs):
        return self

    def tabs(self, titles):
        return [self] * len(titles)

    def columns(self, items, **_kwargs):
        return [self] * (items if isinstance(items, int) else len(items))

    def radio(self, label, options, **_kwargs):
        if label == "Menu":
            return self.page
        return self.session_state.get("tariff_mode_choice", options[0])

    def selectbox(self, _label, options, **_kwargs):
        return list(options)[0]

    def segmented_control(self, _label, _options, **kwargs):
        if _label == "Aparência" and self.theme is not None:
            return self.theme
        return kwargs.get("default")

    def number_input(self, _label, **kwargs):
        return kwargs.get("value", 0)

    def text_input(self, _label, **kwargs):
        return kwargs.get("value", "")

    def text_area(self, _label, **kwargs):
        return kwargs.get("value", "")

    def slider(self, _label, **kwargs):
        return kwargs.get("value", 0)

    def checkbox(self, _label, **kwargs):
        return kwargs.get("value", False)

    def file_uploader(self, _label, **kwargs):
        return UploadedBill(self.upload) if kwargs.get("key") == "copel_pdf_upload" and self.upload is not None else None

    def button(self, _label, **kwargs):
        return (self.apply and kwargs.get("key") == "apply_copel_bill") or (
            self.manual and kwargs.get("key") == "manual_save_now"
        )

    def form_submit_button(self, *_args, **_kwargs):
        return False

    def download_button(self, *_args, **_kwargs):
        return False

    def rerun(self):
        raise RerunRequested()

    def stop(self):
        raise AssertionError("UI unexpectedly stopped")

    def __getattr__(self, _name):
        # Non-interactive display methods irrelevant to this smoke test.
        return lambda *_args, **_kwargs: None


def show_page(monkeypatch, tmp_path, *, page="Início", upload=None, apply=False, theme=None, manual=False):
    fake = FakeStreamlit(page, upload, apply, theme, manual)
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setenv("ENERGY_ESTIMATOR_DATA_DIR", str(tmp_path))
    runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
    return fake


@pytest.mark.parametrize("page", [
    "Início", "Aparelhos", "Calculadora", "Cenários", "Comparações", "Dados e backups",
])
def test_empty_store_all_pages_render_without_missing_api(monkeypatch, tmp_path, page: str) -> None:
    fake = show_page(monkeypatch, tmp_path, page=page)
    assert not [message for kind, message in fake.messages if kind == "error"]
    assert JsonStore(tmp_path).load_tariff().rate == 1.0


def test_bill_upload_previews_without_automatic_save(monkeypatch, tmp_path) -> None:
    raw = (ROOT / "tests/fixtures/copel-danf3e-synthetic.pdf").read_bytes()
    fake = show_page(monkeypatch, tmp_path, upload=raw)
    assert any("Copel reconhecida" in message for kind, message in fake.messages if kind == "success")
    assert ("Tarifa calculada", "R$ 1,000000/kWh") in fake.metrics
    assert not (tmp_path / "settings.json").exists()


def test_explicit_apply_pdf_updates_settings(monkeypatch, tmp_path) -> None:
    raw = (ROOT / "tests/fixtures/copel-danf3e-synthetic.pdf").read_bytes()
    with pytest.raises(RerunRequested):
        show_page(monkeypatch, tmp_path, upload=raw, apply=True)
    tariff = JsonStore(tmp_path).load_tariff()
    assert tariff == Tariff(
        "direct", 1.0, 120.0, 100.0, source="copel_pdf", bill_reference="01/2026"
    )


def test_fallback_apply_saves_bill_mode_and_average(monkeypatch, tmp_path) -> None:
    raw = (ROOT / "tests/fixtures/copel-danf3e-fallback-synthetic.pdf").read_bytes()
    with pytest.raises(RerunRequested):
        show_page(monkeypatch, tmp_path, upload=raw, apply=True)
    tariff = JsonStore(tmp_path).load_tariff()
    assert tariff.source == "copel_pdf"
    assert tariff.mode == "bill"
    assert tariff.bill_reference == "12/2026"
    assert tariff.bill_kwh == 200
    assert tariff.bill_amount == 300
    assert tariff.rate == 1.5


def test_non_copel_pdf_rejected_without_changing_settings(monkeypatch, tmp_path) -> None:
    raw = (ROOT / "tests/fixtures/copel-danf3e-synthetic.pdf").read_bytes()
    # Parseable PDF with valid bytes but extracted issuer replaced using the parser's own text path
    # is tested in test_bill_import. Here the UI validates the rejection and no-write flow.
    fake = show_page(monkeypatch, tmp_path, upload=b"%PDF-1.7\ninvalid", apply=True)
    assert any(kind == "error" for kind, _ in fake.messages)
    assert not (tmp_path / "settings.json").exists()


def test_theme_switch_persists_to_settings_json(monkeypatch, tmp_path) -> None:
    show_page(monkeypatch, tmp_path, page="Aparelhos", theme="dark")
    store = JsonStore(tmp_path)
    assert store.load_theme() == "dark"
    assert store.load_tariff().rate == 1.0
    assert show_page(monkeypatch, tmp_path, page="Dados e backups").page == "Dados e backups"
    assert store.load_theme() == "dark"


def test_manual_save_button_creates_checkpoint(monkeypatch, tmp_path) -> None:
    with pytest.raises(RerunRequested):
        show_page(monkeypatch, tmp_path, page="Dados e backups", manual=True)
    store = JsonStore(tmp_path)
    assert len(list((tmp_path / "backups").glob("manual-*.json"))) == 1
    assert store.load_theme() == "light"
    assert (tmp_path / "settings.json").exists()
    assert (tmp_path / "devices.json").exists()
    assert (tmp_path / "scenarios.json").exists()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_is_rendered_through_streamlit_html(monkeypatch, tmp_path, theme: str) -> None:
    fake = show_page(monkeypatch, tmp_path, theme=theme)
    assert len(fake.html_calls) == 1
    assert fake.html_calls[0].startswith("<style>")
    assert f'data-theme="{theme}"' in fake.html_calls[0]

@pytest.mark.parametrize("page", [
    "Início", "Aparelhos", "Calculadora", "Cenários", "Comparações", "Dados e backups",
])
def test_demo_data_all_pages_render_without_errors(monkeypatch, tmp_path, page: str) -> None:
    """Exercise all routes with actual devices and scenarios, not only an empty store."""
    demo = (ROOT / "examples/backup-demo.json").read_bytes()
    JsonStore(tmp_path).restore_backup(demo)
    fake = show_page(monkeypatch, tmp_path, page=page, theme="dark")
    assert not [message for kind, message in fake.messages if kind == "error"]
    assert len(JsonStore(tmp_path).load_devices()) > 0
    assert len(JsonStore(tmp_path).load_scenarios()) > 0


def test_browser_uses_static_host_css_but_native_keeps_inline_theme(monkeypatch, tmp_path) -> None:
    from energy_estimator import storage
    monkeypatch.setattr(storage, "is_browser_runtime", lambda: True)
    fake = show_page(monkeypatch, tmp_path, theme="light")
    assert any('id="eue-active-theme" data-theme="light"' in item for item in fake.html_calls)
    assert all("<style>" not in item for item in fake.html_calls)
    monkeypatch.setattr(storage, "is_browser_runtime", lambda: False)
    normal = show_page(monkeypatch, tmp_path, theme="light")
    assert any("<style>" in item for item in normal.html_calls)
