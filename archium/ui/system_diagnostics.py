"""System diagnostics — dependency / export tool status for Settings."""

from __future__ import annotations

import shutil

import streamlit as st

from archium.config import get_settings
from archium.ui.llm_settings import get_ui_effective_settings


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


def render_system_diagnostics() -> None:
    """Developer-facing dependency checks for Settings → 系统诊断."""
    pipeline_c, pipeline_h = module_status_pipeline()
    marp_c, marp_h = module_status_marp_export()
    node_c, node_h = module_status_node_pptx()
    render_status("LLM / AI 服务", pipeline_c, pipeline_h)
    render_status("Marp CLI（预览/降级导出）", marp_c, marp_h)
    render_status("Node.js / PptxGen（可编辑 PPTX）", node_c, node_h)


def render_module_status() -> None:
    """Deprecated alias — use ``render_system_diagnostics``."""
    render_system_diagnostics()
