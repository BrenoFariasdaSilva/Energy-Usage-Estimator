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

_THEME_RULES = """

    /* Streamlit uses its own theme tokens on nested layout surfaces. Update the
       tokens as well as explicit containers so switching is not just recoloring
       the cards while leaving the page on the server's static native theme. */
    :root, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
        --background-color: var(--eue-background);
        --secondary-background-color: var(--eue-surface);
        --text-color: var(--eue-text);
        --primary-color: var(--eue-accent);
        --border-color: var(--eue-border);
    }
    :root { color-scheme: var(--eue-color-scheme); }
    html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"],
    [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
        background: var(--eue-background) !important; color: var(--eue-text) !important;
    }
    /* The main section and its inner wrappers can paint over stApp itself.
       They must follow the selected theme, including Streamlit's newer layout. */
    [data-testid="stAppViewContainer"] > section,
    [data-testid="stAppViewContainer"] > div,
    [data-testid="stMain"] > div,
    [data-testid="stMain"] > section,
    [data-testid="stMainBlockContainer"],
    section.main,
    .main > div:first-child {
        background-color: var(--eue-background) !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stHeader"], [data-testid="stToolbar"] {
        background: var(--eue-background) !important; color: var(--eue-text) !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
        background-color: var(--eue-sidebar) !important; color: var(--eue-text) !important;
    }
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] > div {
        background-color: var(--eue-sidebar) !important;
    }
    [data-testid="stSidebar"] {border-right: 1px solid var(--eue-border);}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label {
        border: 1px solid var(--eue-border); border-radius: .65rem; padding: .62rem .75rem;
        background: var(--eue-surface); margin-bottom: .18rem; transition: background .18s, border-color .18s;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        background: var(--eue-tint); border-color: var(--eue-accent);
    }
    [data-testid="stApp"] h1, [data-testid="stApp"] h2, [data-testid="stApp"] h3,
    [data-testid="stApp"] h4, [data-testid="stApp"] p,
    [data-testid="stApp"] label, [data-testid="stApp"] li,
    [data-testid="stApp"] [data-testid="stMarkdownContainer"],
    [data-testid="stApp"] [data-testid="stWidgetLabel"] {color: var(--eue-text);}
    [data-testid="stApp"] [data-testid="stCaptionContainer"],
    [data-testid="stApp"] small {color: var(--eue-muted) !important;}
    [data-testid="stMetric"], [data-testid="stExpander"],
    [data-testid="stForm"], [data-testid="stDataFrame"] {
        background: var(--eue-surface) !important;
        border: 1px solid var(--eue-border) !important; border-radius: .85rem !important;
    }
    [data-testid="stMetric"] {padding: 1.05rem 1.2rem !important;}
    [data-testid="stMetricValue"] {color: var(--eue-text) !important;}
    /* Sidebar tariff: size the entire value to the card, not to the viewport.
       Container units track the actual card width when the sidebar is resized. */
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        container-type: inline-size;
        min-width: 0;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        min-width: 0;
        width: 100%;
        font-size: 1rem !important; /* fallback for browsers without cqi */
        font-size: clamp(.65rem, 10cqi, 1.5rem) !important;
        line-height: 1.25;
        white-space: nowrap;
        overflow: visible !important;
        text-overflow: clip !important;
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] > div {
        min-width: 0;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div,
    div[data-baseweb="select"] > div, div[data-baseweb="base-input"],
    [data-testid="stDateInput"] > div, [data-testid="stNumberInput"] > div {
        background-color: var(--eue-surface) !important;
        color: var(--eue-text) !important; border-color: var(--eue-border) !important;
    }
    [data-testid="stApp"] input, [data-testid="stApp"] textarea,
    [data-testid="stApp"] div[data-baseweb="select"] span,
    [data-testid="stApp"] div[data-baseweb="select"] input {
        color: var(--eue-text) !important; -webkit-text-fill-color: var(--eue-text);
    }
    [data-testid="stApp"] input::placeholder, [data-testid="stApp"] textarea::placeholder {
        color: var(--eue-muted) !important;
    }
    /* The editable number field is itself a painted surface in Streamlit/BaseWeb.
       Painting only its outer div left a WHITE native input with WHITE text
       when the application selected dark but Streamlit's base theme was light.
       Keep the field, its BaseWeb wrapper, and the text/caret in one palette. */
    [data-testid="stApp"] [data-testid="stNumberInput"] input,
    [data-testid="stApp"] [data-testid="stNumberInput"] div[data-baseweb="input"],
    [data-testid="stApp"] [data-testid="stNumberInput"] div[data-baseweb="base-input"],
    [data-testid="stApp"] [data-testid="stNumberInput"] div[data-baseweb="input"] > div,
    [data-testid="stApp"] [data-testid="stNumberInput"] div[data-baseweb="base-input"] > div {
        background-color: var(--eue-surface) !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stNumberInput"] input {
        -webkit-text-fill-color: var(--eue-text) !important;
        caret-color: var(--eue-text) !important;
        color-scheme: var(--eue-color-scheme);
    }
    [data-testid="stApp"] div[data-baseweb="select"] svg {fill: var(--eue-muted);}
    [data-testid="stApp"] [data-testid="stBaseButton-primary"] {
        background-color: var(--eue-accent) !important; color: var(--eue-accent-label) !important;
        border-color: var(--eue-accent) !important; border-radius: .6rem;
    }
    [data-testid="stApp"] [data-testid="stBaseButton-primary"]:hover {
        background-color: var(--eue-accent-hover) !important; border-color: var(--eue-accent-hover) !important;
    }
    [data-testid="stApp"] [data-testid^="stBaseButton-secondary"] {
        background: var(--eue-surface) !important; color: var(--eue-text) !important;
        border-color: var(--eue-border) !important; border-radius: .6rem;
    }
    [data-testid="stApp"] [data-testid="stDownloadButton"] button {
        border-radius: .6rem;
    }
    [data-testid="stApp"] [data-testid="stSegmentedControl"] button,
    [data-testid="stApp"] [data-testid="stTabs"] [role="tab"] {
        color: var(--eue-text) !important; background-color: var(--eue-surface) !important;
        border-color: var(--eue-border) !important;
    }
    [data-testid="stApp"] [data-testid="stSegmentedControl"] button[aria-checked="true"],
    [data-testid="stApp"] [data-testid="stSegmentedControl"] button[aria-pressed="true"],
    [data-testid="stApp"] [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        background-color: var(--eue-tint) !important; color: var(--eue-accent) !important;
        border-color: var(--eue-accent) !important;
    }
    [data-testid="stApp"] [data-testid="stSlider"] {accent-color: var(--eue-accent);}
    [data-testid="stApp"] input[type="checkbox"],
    [data-testid="stApp"] input[type="radio"] {accent-color: var(--eue-accent);}
    [data-testid="stApp"] [data-testid="stNotification"] {
        color: var(--eue-text) !important; border-color: var(--eue-border) !important;
    }
    [data-testid="stApp"] [data-testid="stCodeBlock"],
    [data-testid="stApp"] pre {
        background: var(--eue-surface-alt) !important; color: var(--eue-text) !important;
        border: 1px solid var(--eue-border) !important; border-radius: .65rem;
    }
    /* Native Streamlit status banners and expanders have their own light
       backgrounds. Override the background AND all nested text together. */
    [data-testid="stApp"] [data-testid="stAlert"],
    [data-testid="stApp"] [role="alert"] {
        background: var(--eue-surface-alt) !important;
        color: var(--eue-text) !important;
        border: 1px solid var(--eue-border) !important;
        border-radius: .65rem !important;
    }
    [data-testid="stApp"] [data-testid="stAlert"] *,
    [data-testid="stApp"] [role="alert"] * {
        color: var(--eue-text) !important;
        -webkit-text-fill-color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stExpander"] details,
    [data-testid="stApp"] [data-testid="stExpander"] summary,
    [data-testid="stApp"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background: var(--eue-surface) !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stExpander"] summary *,
    [data-testid="stApp"] [data-testid="stExpander"] summary svg {
        color: var(--eue-text) !important;
        fill: var(--eue-text) !important;
        -webkit-text-fill-color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stFileUploader"] section,
    [data-testid="stApp"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
        background: var(--eue-surface-alt) !important;
        border-color: var(--eue-border) !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stFileUploader"] section *,
    [data-testid="stApp"] [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] * {
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stFileUploader"] button {
        background: var(--eue-surface) !important;
        color: var(--eue-text) !important;
        border: 1px solid var(--eue-border) !important;
    }
    /* The uploaded-file info chip is independently styled by the native
       Streamlit theme. Remove its native (often white) inner backgrounds,
       retaining the outer file-row background from the selected app theme.
       The icon subtree is deliberately EXCLUDED: changing its internal SVG
       paints previously made the document glyph disappear in light mode. */
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] {
        background-color: var(--eue-surface-alt) !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] div:not([data-testid="stFileUploaderFileIcon"]):not([data-testid="stFileUploaderFileIcon"] *) {
        background-color: transparent !important;
        color: var(--eue-text) !important;
    }
    /* Some Streamlit versions paint a pill around the details themselves. */
    [data-testid="stApp"] [data-testid="stFileUploaderFileData"],
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] :is(button, span):has([data-testid="stFileUploaderFileName"]) {
        background-color: transparent !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] :is(p, small, span),
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileName"],
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileSize"] {
        color: var(--eue-text) !important;
        -webkit-text-fill-color: var(--eue-text) !important;
    }
    /* Streamlit may put the test ID on an icon wrapper OR directly on the
       SVG. In either case set foreground color only and preserve the SVG's
       original fill/stroke drawing model (some icons use fill, others stroke).
       Do NOT force SVG fill:none or overwrite all descendant path strokes. */
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileIcon"] {
        background-color: var(--eue-icon-bg) !important;
        color: var(--eue-icon-fg) !important;
        border-radius: .4rem;
    }
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileIcon"] svg,
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] svg[data-testid="stFileUploaderFileIcon"],
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] [data-testid="stFileUploaderFileIcon"] svg *,
    [data-testid="stApp"] [data-testid="stFileUploaderFile"] svg[data-testid="stFileUploaderFileIcon"] * {
        color: var(--eue-icon-fg) !important;
    }
    [data-testid="stApp"] [data-testid="stAlert"] > div,
    [data-testid="stApp"] [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
    [data-testid="stApp"] [role="alert"] > div {
        background-color: transparent !important;
        color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stAlert"] p,
    [data-testid="stApp"] [data-testid="stAlert"] span,
    [data-testid="stApp"] [role="alert"] p,
    [data-testid="stApp"] [role="alert"] span {
        color: var(--eue-text) !important;
        -webkit-text-fill-color: var(--eue-text) !important;
    }
    [data-testid="stApp"] [data-testid="stDataFrame"] *,
    [data-testid="stApp"] [data-testid="stTable"] * {
        /* Data grids retain native cell coloring for legibility. */
        color-scheme: var(--eue-color-scheme);
    }
    [data-testid="stApp"] :focus-visible {
        outline: 2px solid var(--eue-accent) !important;
        outline-offset: 2px;
    }
    [data-testid="stApp"] hr {border-color: var(--eue-border) !important;}
    [data-testid="stApp"] a {color: var(--eue-accent);}
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1430px;}
    .block-container h1 {letter-spacing: -.035em;}
    .eue-hero {
        border: 1px solid var(--eue-border); border-radius: 1rem;
        background: linear-gradient(115deg, var(--eue-tint) 0%, var(--eue-surface) 75%);
        padding: clamp(1.6rem, 3.3vw, 3rem); margin: .2rem 0 1.5rem;
    }
    .eue-eyebrow {color: var(--eue-accent); font-size: .78rem; letter-spacing: .12em;
        font-weight: 800; text-transform: uppercase; margin-bottom: .8rem;}
    .eue-hero h1 {color: var(--eue-text); font-weight: 750; font-size: clamp(1.7rem, 3vw, 2.6rem);
        line-height: 1.2; margin: .25rem 0 .8rem;}
    .eue-hero p {color: var(--eue-muted); max-width: 58rem; font-size: 1rem; margin: 0;}
    .eue-status {border: 1px solid var(--eue-border); border-radius: .65rem;
        background: var(--eue-surface-alt); color: var(--eue-text); padding: .7rem .85rem; font-size: .85rem;}
    .eue-status strong {color: var(--eue-accent);}

"""


def theme_css(theme: str) -> str:
    """Theme CSS and its single state marker; suitable for ``st.html``.

    The same style rules are returned for both appearances. The marker alone
    changes, so a rerun cannot leave stale, competing dark/light rules.
    """
    if theme not in THEMES:
        raise ValueError("Tema desconhecido.")
    return (
        "<style>\n" + _THEME_PALETTE_CSS + _THEME_RULES + "\n</style>"
        + f'<span id="eue-active-theme" data-theme="{escape(theme)}" '
        + 'hidden aria-hidden="true"></span>'
    )

def browser_theme_marker(theme: str) -> str:
    """Expose the saved browser appearance without injecting a competing stylesheet.

    On GitHub Pages the host page owns the CSS. This marker is a fallback if a
    Stlite/Streamlit version changes its segmented-control DOM structure.
    """
    if theme not in THEMES:
        raise ValueError("Tema desconhecido.")
    return f'<span id="eue-active-theme" data-theme="{escape(theme)}" hidden aria-hidden="true"></span>'
