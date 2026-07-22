"""Shared Streamlit UI bootstrap and styling."""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from archium.config import get_settings
from archium.infrastructure.database.session import close_scoped_session, init_database
from archium.logging import setup_logging
from archium.ui.llm_settings import get_ui_effective_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

ARCHIUM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600&family=Source+Serif+4:wght@600&display=swap');

:root {
    --archium-ink: #1a1a1a;
    --archium-muted: #8a8780;
    --archium-line: #e8e6e1;
    --archium-surface: #f7f6f3;
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
}

html, body, [class*="css"] {
    font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
    color: var(--archium-ink);
}

[data-testid="stSidebar"] {
    background-color: var(--archium-surface);
    border-right: 1px solid var(--archium-line);
}

[data-testid="stSidebar"] .block-container {
    padding-top: 2rem;
}

.archium-logo {
    font-family: 'Source Serif 4', 'Times New Roman', serif;
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

.status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.55rem 0;
    border-bottom: 1px solid #eceae4;
    font-size: 0.85rem;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.dot-green  { background: #4a9e6e; box-shadow: 0 0 6px #4a9e6e88; }
.dot-yellow { background: #c4a035; box-shadow: 0 0 6px #c4a03588; }
.dot-red    { background: #c45c5c; box-shadow: 0 0 6px #c45c5c88; }

/* Accessible status chips: text + color + border (not emoji-only). */
.status-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.12rem 0.5rem;
    border-radius: 2px;
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

.section-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #aaa8a2;
    margin: 1.5rem 0 0.6rem 0;
}

[data-testid="stChatMessage"] {
    border-bottom: 1px solid #f0eeea;
    padding-bottom: 1rem;
}

div[data-testid="stChatInput"] textarea {
    border: 1px solid #ddd9d0 !important;
    border-radius: 2px !important;
    background: #fafaf8 !important;
}

.stDownloadButton button {
    border: 1px solid var(--archium-ink) !important;
    background: transparent !important;
    color: var(--archium-ink) !important;
    border-radius: 2px !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.04em;
}
</style>
"""


def init_app() -> None:
    """Initialize environment, logging, and database once per session."""
    close_scoped_session()
    if st.session_state.get("_archium_initialized"):
        return
    load_dotenv()
    setup_logging(get_settings())
    init_database()
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
    """Version / product identity details (Settings → About)."""
    from archium.ui.branding import (
        BRAND_SUBTITLE_CN,
        BRAND_SUBTITLE_EN,
        DISPLAY_VERSION,
        FULL_VERSION_LABEL,
        PRODUCT_NAME_CN,
        SIDEBAR_VALUE_HINT,
    )

    st.markdown("### 关于 Archium")
    st.markdown(f"**{PRODUCT_NAME_CN}**")
    st.caption(f"{BRAND_SUBTITLE_EN} · {BRAND_SUBTITLE_CN}")
    st.markdown(
        f"- 显示版本：`{DISPLAY_VERSION}`\n"
        f"- 完整版本：`{FULL_VERSION_LABEL}`\n"
        f"- 工作方式：{SIDEBAR_VALUE_HINT}"
    )
    st.caption("本地优先：项目与草稿保存在本机，可随时继续编辑。")


def render_status(name: str, color: str, hint: str) -> None:
    st.markdown(
        f'<div class="status-row">'
        f"<span>{name}</span>"
        f'<span><span class="status-dot dot-{color}"></span>{hint}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def module_status_pipeline() -> tuple[str, str]:
    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        return "red", "缺少 API Key"
    return "green", "就绪"


def module_status_marp_export() -> tuple[str, str]:
    settings = get_settings()
    if not shutil.which(settings.marp_command):
        return "yellow", "待安装 Marp CLI"
    return "green", "就绪"


def module_status_legacy_ppt() -> tuple[str, str]:
    settings = get_ui_effective_settings()
    if not settings.llm_configured:
        return "red", "缺少 API Key"
    if not shutil.which(settings.marp_command):
        return "yellow", "待安装 Marp CLI"
    return "green", "就绪"


def render_module_status() -> None:
    """Deprecated alias — use ``render_system_diagnostics`` in Settings."""
    render_system_diagnostics()


def render_system_diagnostics() -> None:
    """Developer-facing dependency checks for Settings → 系统诊断."""
    pipeline_c, pipeline_h = module_status_pipeline()
    marp_c, marp_h = module_status_marp_export()
    legacy_c, legacy_h = module_status_legacy_ppt()
    node_c, node_h = module_status_node_pptx()
    render_status("LLM / AI 服务", pipeline_c, pipeline_h)
    render_status("Marp CLI（预览/降级导出）", marp_c, marp_h)
    render_status("Node.js / PptxGen（可编辑 PPTX）", node_c, node_h)
    render_status("Legacy 快速 PPT", legacy_c, legacy_h)


def module_status_node_pptx() -> tuple[str, str]:
    """Check Node.js + bundled pptxgenjs install (via CLI runner, not renderer)."""
    from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner

    if not shutil.which("node") and not shutil.which("node.exe"):
        return "yellow", "待安装 Node.js"
    try:
        available = PptxGenCliRunner(get_settings()).is_available()
    except Exception:
        return "yellow", "待 npm install（pptxgen）"
    if not available:
        return "yellow", "待 npm install（pptxgen）"
    return "green", "就绪"
