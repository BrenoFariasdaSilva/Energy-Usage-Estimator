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
    assert store.load_theme() == "dark"
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
    assert snapshot["appearance"] == "dark"
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


def test_restore_legacy_backup_without_theme_uses_dark(tmp_path: Path) -> None:
    store = JsonStore(tmp_path)
    store.save_theme("dark")
    backup = json.loads(store.backup_bytes())
    del backup["appearance"]
    store.restore_backup(json.dumps(backup).encode("utf-8"))
    assert store.load_theme() == "dark"


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


def test_css_palette_has_all_expected_colors() -> None:
    for name, colors in THEMES.items():
        css = theme_css(name)
        assert css.startswith("<style>") and '</style><span id="eue-active-theme"' in css
        assert f'data-theme="{name}"' in css
        for value in (colors.background, colors.sidebar, colors.surface, colors.text, colors.accent):
            assert value in css
    assert theme_css("light") != theme_css("dark")
    with pytest.raises(ValueError):
        theme_css("unknown")


def test_chart_theme_does_not_mutate_input_figure() -> None:
    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Bar(x=["A", "B"], y=[4, 1])])
    light = style_chart(fig, "light")
    dark = style_chart(fig, "dark")
    assert light.layout.paper_bgcolor == THEMES["light"].surface
    assert dark.layout.paper_bgcolor == THEMES["dark"].surface
    assert fig.layout.paper_bgcolor is None
    assert light is not dark and dark is not fig
    with pytest.raises(ValueError):
        style_chart(fig, "unknown")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_sidebar_tariff_resizes_without_ellipsis(theme: str) -> None:
    css = theme_css(theme)
    assert '[data-testid="stSidebar"] [data-testid="stMetric"]' in css
    assert 'container-type: inline-size' in css
    assert 'font-size: clamp(.65rem, 10cqi, 1.5rem)' in css
    assert 'text-overflow: clip !important' in css
    assert 'white-space: nowrap' in css

@pytest.mark.parametrize("theme", ["light", "dark"])
def test_native_streamlit_widgets_use_matching_theme_contrast(theme: str) -> None:
    css = theme_css(theme)
    colors = THEMES[theme]
    assert '[data-testid="stAlert"]' in css
    assert '[data-testid="stExpander"] summary' in css
    assert '[data-testid="stFileUploader"] section' in css
    assert f'--eue-surface-alt: {colors.surface_alt};' in css
    assert f'--eue-text: {colors.text};' in css
    assert f'--eue-border: {colors.border};' in css
    assert 'background: var(--eue-surface-alt) !important;' in css
    assert 'color: var(--eue-text) !important;' in css
    assert '[data-testid="stButtonGroup"] [role="radio"]' in css
    assert '[role="radio"][aria-checked="true"]' in css


def test_both_themes_use_blue_accents() -> None:
    for theme in THEMES.values():
        r, g, b = (int(theme.accent[i:i+2], 16) for i in (1, 3, 5))
        assert b > r and b >= g

@pytest.mark.parametrize("name", ["light", "dark"])
def test_theme_switch_updates_main_and_sidebar_surfaces(name: str) -> None:
    css = theme_css(name)
    colors = THEMES[name]
    assert f"--eue-background: {colors.background};" in css
    assert f"--eue-surface: {colors.surface};" in css
    assert '--background-color: var(--eue-background);' in css
    assert '[data-testid="stMain"] > div' in css
    assert '[data-testid="stAppViewContainer"] > section' in css
    assert '[data-testid="stSidebar"] > div' in css
    assert "background-color: var(--eue-sidebar) !important" in css
    assert f'data-theme="{name}"' in css

@pytest.mark.parametrize("theme", ["light", "dark"])
def test_uploaded_file_and_alert_text_contrast_regression(theme: str) -> None:
    css = theme_css(theme)
    assert '[data-testid="stFileUploaderFile"] svg' in css
    assert '[data-testid="stAlert"] p' in css
    assert '[data-testid="stAlert"] > div' in css
    # Never overwrite a native filled-file glyph with line-only stroke rules.
    assert 'stroke: currentColor;' not in css


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_uploaded_file_name_and_icon_have_explicit_contrast(theme: str) -> None:
    css = theme_css(theme)
    assert '[data-testid="stFileUploaderFileName"]' in css
    assert '[data-testid="stFileUploaderFileSize"]' in css
    assert '[data-testid="stFileUploaderFileIcon"] svg' in css
    assert 'background-color: var(--eue-icon-bg) !important' in css
    assert 'color: var(--eue-icon-fg) !important' in css
    assert '[data-testid="stFileUploaderFileData"]' in css
    assert '[data-testid="stNumberInput"] input' in css
    assert 'background-color: transparent !important' in css


def test_theme_css_rules_stay_constant_across_appearance_changes() -> None:
    """Regression: switching one stylesheet for another caused stale CSS."""
    light = theme_css("light")
    dark = theme_css("dark")
    assert light.split('</style>')[0] == dark.split('</style>')[0]
    assert 'data-theme="light"' in light
    assert 'data-theme="dark"' in dark
    assert ':root:has(#eue-active-theme[data-theme="dark"])' in dark
    assert 'background: var(--eue-background) !important' in light
    assert 'data-testid="stFileUploaderFileIcon"] > div' not in light


def test_number_input_has_matching_background_foreground_and_caret() -> None:
    """The outer BaseWeb div alone cannot recolor the editable HTML input."""
    css = theme_css("dark")
    selector = '[data-testid="stApp"] [data-testid="stNumberInput"] input'
    assert selector in css
    rule = css[css.index(selector):]
    assert 'background-color: var(--eue-surface) !important;' in rule.split('}', 1)[0]
    assert '-webkit-text-fill-color: var(--eue-text) !important;' in rule
    assert 'caret-color: var(--eue-text) !important;' in rule


def test_filename_container_cannot_retain_native_light_background() -> None:
    """Streamlit's inner file-details chip must not stay white in dark mode."""
    css = theme_css("dark")
    assert '[data-testid="stFileUploaderFileData"]' in css
    assert 'background-color: transparent !important;' in css
    assert ':not([data-testid="stFileUploaderFileIcon"] *)' in css
    assert '[data-testid="stFileUploaderFileName"]' in css


def test_native_document_icon_is_not_forced_to_stroke_only() -> None:
    """Filled and stroked Streamlit document glyphs both remain visible."""
    css = theme_css("light")
    assert '[data-testid="stFileUploaderFileIcon"] svg *' in css
    assert 'color: var(--eue-icon-fg) !important;' in css
    assert 'fill: none;' not in css
    assert 'stroke: currentColor;' not in css
