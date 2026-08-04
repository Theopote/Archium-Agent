"""Shared Streamlit UI styling and branding helpers."""

from __future__ import annotations

import streamlit as st

ARCHIUM_CSS = """
<style>
:root {
    --archium-ink: #1a1a1a;
    --archium-muted: #6f6c64;
    --archium-line: #c9c4b8;
    --archium-control-border: #b5b0a4;
    --archium-surface: #f0eee8;
    --archium-surface-raised: #ffffff;
    --archium-accent: #2c2a26;
    --archium-accent-hover: #1a1a1a;
    --archium-ok: #1f6b45;
    --archium-ok-bg: #eef7f1;
    --archium-ok-border: #9ecbb0;
    --archium-info: #3d5a80;
    --archium-info-bg: #eef3f8;
    --archium-info-border: #a8bdd4;
    --archium-warn: #7a5c12;
    --archium-warn-bg: #faf4e4;
    --archium-warn-border: #d4bc6a;
    --archium-error: #8a3030;
    --archium-error-bg: #f8ecec;
    --archium-error-border: #d4a0a0;
    --archium-radius: 2px;
    --archium-font-sans: "Segoe UI", "PingFang SC", "Hiragino Sans GB",
        "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
    --archium-font-serif: "Palatino Linotype", "Book Antiqua", "Songti SC",
        "Noto Serif SC", Georgia, serif;
}

html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stCaption {
    font-family: var(--archium-font-sans);
    color: var(--archium-ink);
}

/* —— Sidebar —— */
[data-testid="stSidebar"] {
    background-color: #e9e6df;
    border-right: 1px solid var(--archium-line);
}
[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}
[data-testid="stSidebarNav"] a {
    border-radius: var(--archium-radius);
}
[data-testid="stSidebarNav"] a[aria-selected="true"],
[data-testid="stSidebarNav"] span[aria-selected="true"],
[data-testid="stSidebarNav"] a:has([data-testid="stMarkdownContainer"]) {
    /* selected nav: Streamlit variants differ by version */
}
[data-testid="stSidebarNav"] li[aria-selected="true"] a,
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: #efece6 !important;
    border-left: 2px solid var(--archium-ink);
    font-weight: 600;
}

/* —— Brand —— */
.archium-logo {
    font-family: var(--archium-font-serif);
    font-size: 1.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--archium-ink);
    margin-bottom: 0.15rem;
}
.archium-sub {
    font-size: 0.78rem;
    font-weight: 300;
    letter-spacing: 0.04em;
    color: var(--archium-muted);
    margin-bottom: 2rem;
}

/* —— Page header —— */
.archium-page-header {
    margin: 0 0 0.25rem 0;
}
.archium-page-title {
    font-family: var(--archium-font-serif);
    font-size: 1.55rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--archium-ink);
    margin: 0;
    line-height: 1.25;
}
.archium-page-caption {
    margin: 0.15rem 0 0.75rem 0;
    font-size: 0.9rem;
    color: var(--archium-muted);
    line-height: 1.45;
}

/* —— Stepper —— */
.archium-stepper {
    display: block;
    padding: 0.45rem 0.65rem;
    margin: 0 0 1rem 0;
    background: var(--archium-surface);
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    font-size: 0.82rem;
    color: var(--archium-muted);
    letter-spacing: 0.01em;
}
.archium-stepper strong {
    color: var(--archium-ink);
    font-weight: 600;
}

/* —— Panel / card —— */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--archium-surface-raised) !important;
    border: 1px solid var(--archium-line) !important;
    border-radius: var(--archium-radius) !important;
    box-shadow: 0 1px 0 rgba(44, 42, 38, 0.04);
}
.archium-panel-title {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--archium-muted);
    margin: 0 0 0.6rem 0;
}

/* —— Inspector —— */
.archium-inspector-section {
    margin: 0.35rem 0 0.5rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--archium-line);
}
.archium-inspector-title {
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--archium-ink);
}

/* —— Toolbar —— */
.archium-toolbar {
    margin: 0.25rem 0 0.75rem 0;
}

/* —— Empty state —— */
.archium-empty {
    text-align: left;
    padding: 1.25rem 0.25rem 0.75rem 0;
}
.archium-empty-title {
    font-family: var(--archium-font-serif);
    font-size: 1.35rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.archium-empty-body {
    color: var(--archium-muted);
    font-size: 0.92rem;
    line-height: 1.5;
    margin: 0 0 0.85rem 0;
}

/* —— Callouts —— */
.archium-callout {
    padding: 0.65rem 0.85rem;
    margin: 0.4rem 0 0.75rem 0;
    border-radius: var(--archium-radius);
    border: 1px solid transparent;
    font-size: 0.88rem;
    line-height: 1.45;
}
.archium-callout-warn {
    color: var(--archium-warn);
    background: var(--archium-warn-bg);
    border-color: var(--archium-warn-border);
}
.archium-callout-draft {
    color: #7a4a00;
    background: #fff4e0;
    border-color: #e0b45c;
    border-width: 1px;
    border-left-width: 4px;
    font-weight: 500;
}
.archium-callout-draft strong {
    display: block;
    font-size: 0.95rem;
    margin-bottom: 0.15rem;
}
.archium-callout-info {
    color: var(--archium-info);
    background: var(--archium-info-bg);
    border-color: var(--archium-info-border);
}
.archium-callout-error {
    color: var(--archium-error);
    background: var(--archium-error-bg);
    border-color: var(--archium-error-border);
}

/* —— Status row / chips —— */
.status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--archium-line);
    font-size: 0.85rem;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.dot-green  { background: #4a9e6e; }
.dot-yellow { background: #c4a035; }
.dot-red    { background: #c45c5c; }

/* —— App canvas —— */
.stApp {
    background: var(--archium-surface);
}
.stApp [data-testid="stAppViewContainer"] > .main {
    background: var(--archium-surface);
}
.block-container {
    padding-top: 1.75rem;
    padding-bottom: 3rem;
}

.archium-stat-chip-row,
.archium-status-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.35rem 0 0.65rem 0;
}
.archium-stat-chip {
    display: inline-flex;
    flex-direction: column;
    gap: 0.08rem;
    min-width: 5.5rem;
    padding: 0.35rem 0.55rem;
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    background: var(--archium-surface-raised);
}
.archium-stat-chip-label {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--archium-muted);
}
.archium-stat-chip-value {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--archium-ink);
    line-height: 1.25;
}
.archium-stat-chip-ok { border-color: var(--archium-ok-border); background: var(--archium-ok-bg); }
.archium-stat-chip-ok .archium-stat-chip-value { color: var(--archium-ok); }
.archium-stat-chip-warn { border-color: var(--archium-warn-border); background: var(--archium-warn-bg); }
.archium-stat-chip-warn .archium-stat-chip-value { color: var(--archium-warn); }
.archium-stat-chip-error { border-color: var(--archium-error-border); background: var(--archium-error-bg); }
.archium-stat-chip-error .archium-stat-chip-value { color: var(--archium-error); }
.archium-stat-chip-info { border-color: var(--archium-info-border); background: var(--archium-info-bg); }
.archium-stat-chip-info .archium-stat-chip-value { color: var(--archium-info); }

.archium-home-hero {
    margin: 0 0 1.1rem 0;
}
.archium-home-hero-title {
    font-family: var(--archium-font-serif);
    font-size: 1.65rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    margin: 0 0 0.25rem 0;
    color: var(--archium-ink);
}
.archium-home-hero-caption {
    margin: 0;
    color: var(--archium-muted);
    font-size: 0.92rem;
    line-height: 1.45;
}
.archium-task-list {
    display: flex;
    flex-direction: column;
    gap: 0;
    margin: 0.35rem 0 0.85rem 0;
    border-top: 1px solid var(--archium-line);
}
.archium-task-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.7rem 0;
    border-bottom: 1px solid var(--archium-line);
}
.archium-task-row-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--archium-ink);
}
.archium-task-row-caption {
    font-size: 0.82rem;
    color: var(--archium-muted);
    margin-top: 0.15rem;
}

.status-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.12rem 0.5rem;
    border-radius: var(--archium-radius);
    border: 1px solid transparent;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    line-height: 1.4;
    white-space: nowrap;
}
.status-chip-mark {
    font-size: 0.72rem;
    font-weight: 600;
    opacity: 0.9;
}
.status-chip-ok {
    color: var(--archium-ok);
    background: var(--archium-ok-bg);
    border-color: var(--archium-ok-border);
}
.status-chip-info {
    color: var(--archium-info);
    background: var(--archium-info-bg);
    border-color: var(--archium-info-border);
}
.status-chip-warn {
    color: var(--archium-warn);
    background: var(--archium-warn-bg);
    border-color: var(--archium-warn-border);
}
.status-chip-error {
    color: var(--archium-error);
    background: var(--archium-error-bg);
    border-color: var(--archium-error-border);
}
.status-chip-neutral {
    color: #5c5a55;
    background: #f3f2ef;
    border-color: #d4d1c8;
}

.page-intelligence-strip {
    margin: 0 0 0.65rem 0;
    padding: 0.55rem 0.75rem;
    background: var(--archium-surface);
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
}
.page-intelligence-title {
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--archium-ink);
    margin-bottom: 0.4rem;
}
.page-intelligence-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}
.page-intel-chip {
    display: inline-flex;
    flex-direction: column;
    gap: 0.05rem;
    padding: 0.2rem 0.45rem;
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    background: var(--archium-surface-raised);
    max-width: 100%;
}
.page-intel-chip-label {
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--archium-muted);
}
.page-intel-chip-value {
    font-size: 0.78rem;
    color: var(--archium-ink);
    line-height: 1.3;
    word-break: break-word;
}

.delivery-check-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.15rem 0;
    border-bottom: 1px solid var(--archium-line);
    font-size: 0.84rem;
}
.delivery-check-detail {
    color: var(--archium-muted);
    font-size: 0.78rem;
    text-align: right;
}

/* Compact horizontal gap between sibling controls */
[data-testid="stHorizontalBlock"] {
    gap: 0.4rem !important;
    row-gap: 0.35rem !important;
}

.first-run-steps {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.65rem 0 0.35rem 0;
}
.first-run-step {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.55rem;
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    font-size: 0.78rem;
    background: var(--archium-surface-raised);
}
.first-run-step-num {
    font-weight: 700;
    font-size: 0.72rem;
}
.first-run-step-done {
    color: var(--archium-ok);
    border-color: var(--archium-ok-border);
    background: var(--archium-ok-bg);
}
.first-run-step-active {
    color: var(--archium-ink);
    border-color: var(--archium-ink);
    font-weight: 600;
}
.first-run-step-todo {
    color: var(--archium-muted);
}


.archium-sidebar-project {
    margin: 0 0 0.45rem 0;
}
.archium-sidebar-project-name {
    font-family: var(--archium-font-serif);
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--archium-ink);
    line-height: 1.3;
}
.archium-sidebar-project-summary {
    margin-top: 0.2rem;
    font-size: 0.78rem;
    color: var(--archium-muted);
    line-height: 1.4;
}
.archium-sidebar-footer {
    margin-top: 2rem;
    font-size: 0.72rem;
    color: #bbb9b2;
    line-height: 1.6;
}

.section-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #7a776f;
    margin: 1.5rem 0 0.6rem 0;
}

/* —— Buttons: primary / secondary / danger —— */
div.stButton > button,
button[data-testid="baseButton-secondary"],
button[kind="secondary"] {
    border: 1px solid var(--archium-control-border) !important;
    background: var(--archium-surface-raised) !important;
    color: var(--archium-ink) !important;
    border-radius: var(--archium-radius) !important;
    font-family: var(--archium-font-sans) !important;
    font-size: 0.86rem !important;
    letter-spacing: 0.02em;
    box-shadow: 0 1px 0 rgba(44, 42, 38, 0.05) !important;
}
div.stButton > button:hover {
    border-color: #8f8a7e !important;
    background: #fafaf7 !important;
}
button[data-testid="baseButton-primary"],
button[kind="primary"],
div.stButton > button[kind="primary"] {
    border: 1px solid var(--archium-accent) !important;
    background: var(--archium-accent) !important;
    color: #fafaf8 !important;
    border-radius: var(--archium-radius) !important;
    font-weight: 500 !important;
    box-shadow: none !important;
}
button[data-testid="baseButton-primary"]:hover,
button[kind="primary"]:hover {
    background: var(--archium-accent-hover) !important;
    border-color: var(--archium-accent-hover) !important;
}
.archium-btn-danger div.stButton > button {
    border-color: var(--archium-error-border) !important;
    color: var(--archium-error) !important;
    background: var(--archium-error-bg) !important;
}

.stDownloadButton button {
    border: 1px solid var(--archium-control-border) !important;
    background: var(--archium-surface-raised) !important;
    color: var(--archium-ink) !important;
    border-radius: var(--archium-radius) !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.04em;
}

/* —— Inputs / tables / dialogs —— */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div,
div[data-testid="stMultiSelect"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stTimeInput"] input {
    border-radius: var(--archium-radius) !important;
    border: 1px solid var(--archium-control-border) !important;
    background: var(--archium-surface-raised) !important;
    color: var(--archium-ink) !important;
    box-shadow: none !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--archium-ink) !important;
    outline: 1px solid rgba(44, 42, 38, 0.18) !important;
}
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
    border: 1px dashed var(--archium-control-border) !important;
    background: var(--archium-surface-raised) !important;
    border-radius: var(--archium-radius) !important;
}
[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    background: var(--archium-surface-raised);
}
div[data-testid="stDialog"],
div[role="dialog"] {
    border-radius: var(--archium-radius) !important;
    border: 1px solid var(--archium-line) !important;
    background: var(--archium-surface-raised) !important;
}
div[data-testid="stPopoverBody"] {
    border-radius: var(--archium-radius) !important;
    border: 1px solid var(--archium-line) !important;
    background: var(--archium-surface-raised) !important;
}

/* —— Tabs / pills / segmented —— */
button[data-baseweb="tab"] {
    color: var(--archium-muted) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--archium-ink) !important;
    border-bottom-color: var(--archium-ink) !important;
}
div[data-testid="stSegmentedControl"] > div,
div[data-testid="stPills"] {
    background: var(--archium-surface-raised) !important;
    border: 1px solid var(--archium-line) !important;
    border-radius: var(--archium-radius) !important;
    padding: 0.15rem !important;
}

/* —— Chat —— */
[data-testid="stChatMessage"] {
    border-bottom: 1px solid var(--archium-line);
    padding-bottom: 1rem;
}
div[data-testid="stChatInput"] textarea {
    border: 1px solid var(--archium-control-border) !important;
    border-radius: var(--archium-radius) !important;
    background: var(--archium-surface-raised) !important;
}

/* —— Metrics (legacy) / expanders —— */
[data-testid="stMetric"] {
    background: var(--archium-surface-raised);
    border: 1px solid var(--archium-line);
    border-radius: var(--archium-radius);
    padding: 0.45rem 0.6rem;
}
[data-testid="stMetricLabel"] {
    color: var(--archium-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.7rem !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--archium-font-serif) !important;
    font-size: 1.15rem !important;
    color: var(--archium-ink) !important;
}
[data-testid="stExpander"] {
    border: 1px solid var(--archium-line) !important;
    border-radius: var(--archium-radius) !important;
    background: var(--archium-surface-raised) !important;
}
[data-testid="stExpander"] details {
    background: var(--archium-surface-raised) !important;
}

/* —— Stat chips sit clearly on cream —— */
.archium-stat-chip {
    border-color: var(--archium-control-border) !important;
    box-shadow: 0 1px 0 rgba(44, 42, 38, 0.04);
}
.status-chip {
    box-shadow: 0 1px 0 rgba(44, 42, 38, 0.03);
}

/* —— Selected / focus —— */
.archium-selected,
button[kind="secondary"][aria-pressed="true"] {
    outline: 2px solid var(--archium-info-border);
    outline-offset: 1px;
}
</style>
"""


def init_app() -> None:
    """Initialize environment, logging, and database once per session.

    Prefer :func:`archium.bootstrap.create_application` for the full product
    shell. This helper remains for pages/tests that only need runtime init.
    """
    from archium.bootstrap import bootstrap_runtime
    from archium.infrastructure.database.session import close_scoped_session

    close_scoped_session()
    if st.session_state.get("_archium_initialized"):
        return
    bootstrap_runtime()
    st.session_state._archium_initialized = True


def inject_styles() -> None:
    st.markdown(ARCHIUM_CSS, unsafe_allow_html=True)


def render_branding() -> None:
    from archium.ui.branding import BRAND_SUBTITLE

    st.markdown('<div class="archium-logo">Archium</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="archium-sub">{BRAND_SUBTITLE}</div>',
        unsafe_allow_html=True,
    )


def render_version_footer() -> None:
    """Compact productized version line for the sidebar."""
    from archium.ui.branding import render_version_footer as _render

    _render()


def render_about_panel() -> None:
    """Compatibility wrapper — prefer ``archium.ui.branding.render_about_panel``."""
    from archium.ui.branding import render_about_panel as _render

    _render()
