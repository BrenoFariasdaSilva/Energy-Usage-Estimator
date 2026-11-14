"""Interactive local-first Streamlit dashboard for household electricity costs."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from energy_estimator.calculations import (  # noqa: E402
    cost_for_hours,
    estimate_scenario,
    format_brl,
    format_number,
    hours_from_duration,
    totals,
)
from energy_estimator.charts import (  # noqa: E402
    cost_by_duration,
    scenario_comparison,
    scenario_energy_donut,
    scenario_period_bar,
)
from energy_estimator.models import Device, Scenario, Tariff, UsageItem, new_id  # noqa: E402
from energy_estimator.bill_import import BillImportError, CopelBill, parse_copel_pdf  # noqa: E402
from energy_estimator.presets import example_devices  # noqa: E402
from energy_estimator.storage import JsonStore, StorageError, data_directory, is_browser_runtime  # noqa: E402
from energy_estimator.ui_theme import browser_theme_marker, style_chart, theme_css  # noqa: E402

BROWSER_MODE = is_browser_runtime()

st.set_page_config(page_title="Energy Usage Estimator", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")


STORE = JsonStore(data_directory(ROOT))
try:
    DEVICES, SCENARIOS, TARIFF = STORE.load_all()
    SAVED_THEME = STORE.load_theme()
except StorageError as exc:
    st.error(f"Não foi possível carregar os dados locais: {exc}")
    st.info("Os arquivos não foram alterados. Corrija ou restaure os JSONs na pasta de dados para continuar.")
    st.stop()


def show_success(message: str) -> None:
    """Show a notification that survives the next Streamlit rerun."""
    st.session_state["notification"] = message
    st.rerun()


def save_or_warn(action, success_message: str) -> None:
    """Handle known user-input and file errors without discarding form state silently."""
    try:
        action()
    except (ValueError, StorageError, OSError) as exc:
        st.error(str(exc))
    else:
        show_success(success_message)


def render_chart(fig) -> None:
    """Use a matching Plotly color scheme instead of Streamlit's independent chart theme."""
    st.plotly_chart(style_chart(fig, ACTIVE_THEME), use_container_width=True, theme=None)


def header(title: str, subtitle: str) -> None:
    """Render a consistent dashboard heading."""
    st.title(title)
    st.caption(subtitle)


def device_label(device: Device) -> str:
    """Describe a device in selection controls."""
    return f"{device.name} · {format_number(device.watts, 0)} W"
