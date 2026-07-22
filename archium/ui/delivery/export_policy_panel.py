"""Export policy selection for the deliver stage."""

from __future__ import annotations

import streamlit as st

from archium.application.export_policy_service import export_policy_from_preset
from archium.domain.export_fidelity import ExportPolicy

EXPORT_POLICY_PRESETS: dict[str, str] = {
    "strict_native": "严格原生可编辑",
    "allow_hybrid": "允许混合可编辑",
    "allow_text_bg": "允许文字可编辑背景",
    "allow_raster": "允许图片式降级",
}

EXPORT_POLICY_SESSION_KEY = "export_policy_preset"


def get_session_export_policy() -> ExportPolicy:
    preset = str(st.session_state.get(EXPORT_POLICY_SESSION_KEY) or "strict_native")
    if preset not in EXPORT_POLICY_PRESETS:
        preset = "strict_native"
    return export_policy_from_preset(preset)


def render_export_policy_panel(*, key_prefix: str = "deliver") -> ExportPolicy:
    """Render export strategy controls; return active policy."""
    st.markdown("#### 导出策略")
    preset_options = list(EXPORT_POLICY_PRESETS.keys())
    current = str(st.session_state.get(EXPORT_POLICY_SESSION_KEY) or "strict_native")
    if current not in preset_options:
        current = "strict_native"

    selected = st.radio(
        "忠实度要求",
        options=preset_options,
        index=preset_options.index(current),
        format_func=lambda key: EXPORT_POLICY_PRESETS[key],
        key=f"{key_prefix}_export_policy_preset",
        horizontal=False,
    )
    st.session_state[EXPORT_POLICY_SESSION_KEY] = selected
    policy = export_policy_from_preset(selected)

    hints = {
        "strict_native": "所有页面必须为原生可编辑对象；禁止静默图片降级。",
        "allow_hybrid": "允许部分页面保留 Bitmap 复杂视觉，但必须逐页披露。",
        "allow_text_bg": "允许背景为图片、文字为可编辑文本框的页面。",
        "allow_raster": "允许整页图片式 PPTX，但必须显式记录降级原因。",
    }
    st.caption(hints.get(selected, ""))
    return policy
