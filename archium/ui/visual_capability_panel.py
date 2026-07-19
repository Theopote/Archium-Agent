"""Streamlit copy for Round 1 visual composition engine scope and limits."""

from __future__ import annotations

import streamlit as st

from archium.ui.label_map import entity_label, visual_quality_pair
from archium.ui.layout_family_ui import (
    FAMILY_SCENARIOS,
    format_layout_family_label,
    implemented_layout_family_definitions,
    planned_layout_family_definitions,
)


def render_visual_engine_scope(*, expanded: bool = False) -> None:
    """Explain what Round 1 layout engine can and cannot do."""
    implemented = implemented_layout_family_definitions()
    planned = planned_layout_family_definitions()
    implemented_count = len(implemented)

    summary = (
        f"当前版式引擎已可用 {implemented_count} 类常见建筑汇报场景"
        "（固定排布规则，非通用约束求解器）。"
        "并非针对任意数量、任意长宽比素材逐页计算「最优」排布；"
        "超出范围时会尝试几何校验/修复或切换候选版式，"
        "未运行视觉编排时导出可退回 PresentationSpec 通用模板。"
    )
    if planned:
        summary += f"另有 {len(planned)} 类版式族已注册但尚未实现，界面会标注「即将支持」。"
    st.info(summary)

    with st.expander("了解版式引擎能力边界", expanded=expanded):
        st.markdown(
            "**Round 1 工作原理：** 为每页选择最匹配的版式族与变体，"
            "再由确定性 generator 按固定规则生成元素坐标；"
            f"PPTX 导出按{entity_label('LayoutPlan')}执行，不会重新求解版式。"
        )

        st.markdown(f"**已可用（{implemented_count} 类）：**")
        implemented_rows = []
        for definition in sorted(implemented, key=lambda item: item.family.value):
            scenario = FAMILY_SCENARIOS.get(definition.family, "—")
            label = format_layout_family_label(definition.family, show_availability=False)
            implemented_rows.append(
                f"- **{label}**（`{definition.family.value}`）：{scenario}"
            )
        st.markdown("\n".join(implemented_rows))

        if planned:
            st.markdown(f"**即将支持（{len(planned)} 类，暂不可选）：**")
            planned_rows = []
            for definition in sorted(planned, key=lambda item: item.family.value):
                label = format_layout_family_label(definition.family, show_availability=True)
                description = definition.description or FAMILY_SCENARIOS.get(definition.family, "—")
                planned_rows.append(f"- **{label}**：{description}")
            st.markdown("\n".join(planned_rows))

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
            f"{visual_quality_pair()} 目前为只读提示，不会自动改稿或阻断导出。"
        )
