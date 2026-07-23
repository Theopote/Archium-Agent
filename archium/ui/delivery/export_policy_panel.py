"""Export policy selection for the deliver stage."""

from __future__ import annotations

import streamlit as st

from archium.application.export_policy_service import export_policy_from_preset
from archium.domain.export_fidelity import (
    CHART_EXPORT_MODE_LABELS_ZH,
    ChartExportMode,
    ExportPolicy,
)

EXPORT_POLICY_PRESETS: dict[str, str] = {
    "strict_native": "严格原生可编辑",
    "allow_hybrid": "允许混合可编辑",
    "allow_text_bg": "允许文字可编辑背景",
    "allow_raster": "允许图片式降级",
}

EXPORT_POLICY_SESSION_KEY = "export_policy_preset"
CHART_EXPORT_MODE_SESSION_KEY = "chart_export_mode"


def get_session_export_policy() -> ExportPolicy:
    preset = str(st.session_state.get(EXPORT_POLICY_SESSION_KEY) or "strict_native")
    if preset not in EXPORT_POLICY_PRESETS:
        preset = "strict_native"
    policy = export_policy_from_preset(preset)
    mode_raw = str(
        st.session_state.get(CHART_EXPORT_MODE_SESSION_KEY)
        or ChartExportMode.CROSS_APP_STABLE.value
    )
    try:
        mode = ChartExportMode(mode_raw)
    except ValueError:
        mode = ChartExportMode.CROSS_APP_STABLE
    return policy.model_copy(update={"chart_export_mode": mode})


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

    st.markdown("##### 图表 / 表格导出")
    mode_options = [mode.value for mode in ChartExportMode]
    current_mode = str(
        st.session_state.get(CHART_EXPORT_MODE_SESSION_KEY)
        or ChartExportMode.CROSS_APP_STABLE.value
    )
    if current_mode not in mode_options:
        current_mode = ChartExportMode.CROSS_APP_STABLE.value
    selected_mode = st.radio(
        "图表模式",
        options=mode_options,
        index=mode_options.index(current_mode),
        format_func=lambda key: CHART_EXPORT_MODE_LABELS_ZH[ChartExportMode(key)],
        key=f"{key_prefix}_chart_export_mode",
        horizontal=False,
    )
    st.session_state[CHART_EXPORT_MODE_SESSION_KEY] = selected_mode
    chart_mode = ChartExportMode(selected_mode)
    mode_hints = {
        ChartExportMode.CROSS_APP_STABLE: (
            "默认：用形状/图片/文本网格表达图表与表格，跨 PowerPoint / Keynote / "
            "LibreOffice / WPS 观感更稳定；不含内嵌工作簿。"
        ),
        ChartExportMode.NATIVE_DATA_BACKED: (
            "可选：导出为可编辑的原生 PowerPoint Chart / Table（图表含内嵌 Excel 工作簿），"
            "便于在 PowerPoint 中改数据；跨应用渲染可能不一致。"
        ),
    }
    st.caption(mode_hints[chart_mode])
    return policy.model_copy(update={"chart_export_mode": chart_mode})
