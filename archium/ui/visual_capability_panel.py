"""Streamlit copy for Round 1 visual composition engine scope and limits."""

from __future__ import annotations

import streamlit as st

from archium.domain.visual.enums import LayoutFamily
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.ui.slide_visual_panel import FAMILY_LABELS

FAMILY_SCENARIOS: dict[LayoutFamily, str] = {
    LayoutFamily.HERO: "封面或开篇，大图配合标题",
    LayoutFamily.EVIDENCE_BOARD: "多张照片/证据网格与说明",
    LayoutFamily.DRAWING_FOCUS: "平面图、剖面、立面等图纸主导",
    LayoutFamily.COMPARATIVE_MATRIX: "多案例并列对比",
    LayoutFamily.PROCESS_NARRATIVE: "时间线或步骤流程",
    LayoutFamily.ANALYTICAL_DIAGRAM: "分析图与标注说明",
    LayoutFamily.METRIC_DASHBOARD: "关键指标与数据摘要",
    LayoutFamily.STRATEGY_CARDS: "分点策略或要点卡片",
    LayoutFamily.TEXTUAL_ARGUMENT: "以文字论述为主",
    LayoutFamily.HYBRID_CANVAS: "图文混合、非标准结构",
}


def _implemented_family_count() -> int:
    return len(get_layout_family_registry().implemented())


def render_visual_engine_scope(*, expanded: bool = False) -> None:
    """Explain what Round 1 layout engine can and cannot do."""
    count = _implemented_family_count()
    st.info(
        f"当前版式引擎覆盖 {count} 类常见建筑汇报场景（固定排布规则，非通用约束求解器）。"
        "并非针对任意数量、任意长宽比素材逐页计算「最优」排布；"
        "超出范围时会尝试几何校验/修复或切换候选版式，"
        "未运行视觉编排时导出可退回 PresentationSpec 通用模板。"
    )

    with st.expander("了解版式引擎能力边界", expanded=expanded):
        st.markdown(
            "**Round 1 工作原理：** 为每页选择最匹配的版式族与变体，"
            "再由确定性 generator 按固定规则生成元素坐标；"
            "PPTX 导出按 LayoutPlan 执行，不会重新求解版式。"
        )

        st.markdown("**已覆盖的常见场景：**")
        rows = []
        for family in LayoutFamily:
            label = FAMILY_LABELS.get(family, family.value)
            scenario = FAMILY_SCENARIOS.get(family, "—")
            rows.append(f"- **{label}**（`{family.value}`）：{scenario}")
        st.markdown("\n".join(rows))

        st.markdown(
            "**超出范围时会发生什么：**\n"
            "- 编排流程内：尝试文字溢出修复、切换变体或候选方案，"
            "必要时自动降级到另一套仍可通过几何校验的版式\n"
            "- 仍无法通过版式审核时：工作流会暂停，需你在「单页视觉」中手动调整\n"
            "- 跳过视觉编排或选择旧路径：使用 PresentationSpec 的 11 种硬编码通用模板导出"
        )

        st.markdown(
            "**Round 1 尚未覆盖：** 完整视觉语言模型审核、复杂约束求解、"
            "自动效果图生成，以及拖拽式逐页定制排布。"
            "Visual Critic / Deck QA 目前为只读提示，不会自动改稿或阻断导出。"
        )
