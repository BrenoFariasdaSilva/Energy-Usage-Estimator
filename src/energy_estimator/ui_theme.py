"""Accessible light/dark Streamlit styling using a single invariant stylesheet.

The appearance selector changes a hidden HTML marker, not an entire replacement CSS
stylesheet. Theme variables then update across Streamlit's layout and native widgets.
This avoids orphaned light/dark rule sets during Streamlit reruns.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import plotly.graph_objects as go


@dataclass(frozen=True)
class ThemeColors:
    background: str
    sidebar: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    accent_label: str
    tint: str
    grid: str


THEMES = {
    "light": ThemeColors(
        background="#F5F9FE", sidebar="#EAF2FB", surface="#FFFFFF", surface_alt="#EFF6FF",
        text="#14283D", muted="#52677F", border="#CBDCEC", accent="#087FC4",
        accent_hover="#05669F", accent_label="#FFFFFF", tint="#DCEFFF", grid="#DDE9F5",
    ),
    "dark": ThemeColors(
        background="#0B121C", sidebar="#121E2C", surface="#142333", surface_alt="#1B3045",
        text="#F1F7FF", muted="#B5C8DC", border="#304A63", accent="#32A9EF",
        accent_hover="#1385CD", accent_label="#071B2B", tint="#153A58", grid="#2A4158",
    ),
}


# One stylesheet is retained regardless of the selected appearance.
# CSS variables follow the marker rendered in the Streamlit document, so a
# rerun only updates one marker instead of swapping hundreds of CSS rules.
_THEME_PALETTE_CSS = """
:root {
    --eue-background: #F5F9FE;
    --eue-sidebar: #EAF2FB;
    --eue-surface: #FFFFFF;
    --eue-surface-alt: #EFF6FF;
    --eue-text: #14283D;
    --eue-muted: #52677F;
    --eue-border: #CBDCEC;
    --eue-accent: #087FC4;
    --eue-accent-hover: #05669F;
    --eue-accent-label: #FFFFFF;
    --eue-tint: #DCEFFF;
    --eue-grid: #DDE9F5;
    --eue-color-scheme: light;
    --eue-icon-bg: #14283D;
    --eue-icon-fg: #FFFFFF;
}
:root:has(#eue-active-theme[data-theme="dark"]) {
    --eue-background: #0B121C;
    --eue-sidebar: #121E2C;
    --eue-surface: #142333;
    --eue-surface-alt: #1B3045;
    --eue-text: #F1F7FF;
    --eue-muted: #B5C8DC;
    --eue-border: #304A63;
    --eue-accent: #32A9EF;
    --eue-accent-hover: #1385CD;
    --eue-accent-label: #071B2B;
    --eue-tint: #153A58;
    --eue-grid: #2A4158;
    --eue-color-scheme: dark;
    --eue-icon-bg: #243F59;
    --eue-icon-fg: #F1F7FF;
}
"""
