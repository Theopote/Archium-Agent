"""Layout family display helpers for Streamlit selection surfaces."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutFamily
from archium.infrastructure.layout.layout_family_registry import (
    LayoutFamilyDefinition,
    get_layout_family_registry,
)
from archium.ui.availability_labels import append_coming_soon_suffix

FAMILY_LABELS: dict[LayoutFamily, str] = {
    LayoutFamily.HERO: "主视觉页",
    LayoutFamily.EVIDENCE_BOARD: "证据板",
    LayoutFamily.DRAWING_FOCUS: "图纸主导",
    LayoutFamily.COMPARATIVE_MATRIX: "案例比较",
    LayoutFamily.PROCESS_NARRATIVE: "过程叙事",
    LayoutFamily.ANALYTICAL_DIAGRAM: "分析图",
    LayoutFamily.METRIC_DASHBOARD: "指标看板",
    LayoutFamily.STRATEGY_CARDS: "策略卡片",
    LayoutFamily.TEXTUAL_ARGUMENT: "文字论述",
    LayoutFamily.HYBRID_CANVAS: "混合画布",
}

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


def layout_family_implemented(family: LayoutFamily) -> bool:
    return get_layout_family_registry().get(family).implemented


def implemented_layout_family_definitions() -> list[LayoutFamilyDefinition]:
    return get_layout_family_registry().implemented()


def planned_layout_family_definitions() -> list[LayoutFamilyDefinition]:
    return [item for item in get_layout_family_registry().all() if not item.implemented]


def format_layout_family_label(
    family: LayoutFamily,
    *,
    include_code: bool = False,
    show_availability: bool = True,
) -> str:
    """Human label for a layout family, with optional availability marker."""
    label = FAMILY_LABELS.get(family, family.value)
    if include_code:
        label = f"{label}（{family.value}）"
    if show_availability and not layout_family_implemented(family):
        label = append_coming_soon_suffix(label)
    return label


def layout_family_availability_status(family: LayoutFamily) -> str:
    return "可用" if layout_family_implemented(family) else "即将支持"
