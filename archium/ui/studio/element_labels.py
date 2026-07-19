"""User-facing labels for layout element roles."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole

ROLE_LABELS: dict[LayoutElementRole, str] = {
    LayoutElementRole.TITLE: "标题",
    LayoutElementRole.SUBTITLE: "副标题",
    LayoutElementRole.LEAD_STATEMENT: "引导语",
    LayoutElementRole.HERO_VISUAL: "主视觉",
    LayoutElementRole.SUPPORTING_VISUAL: "辅助图",
    LayoutElementRole.BODY_TEXT: "正文",
    LayoutElementRole.METRIC: "指标",
    LayoutElementRole.CAPTION: "图注",
    LayoutElementRole.ANNOTATION: "标注",
    LayoutElementRole.SOURCE: "来源",
    LayoutElementRole.FOOTER: "页脚",
    LayoutElementRole.PAGE_NUMBER: "页码",
    LayoutElementRole.DECORATION: "装饰",
}

CONTENT_TYPE_LABELS: dict[LayoutContentType, str] = {
    LayoutContentType.TEXT: "文字",
    LayoutContentType.IMAGE: "图片",
    LayoutContentType.DRAWING: "图纸",
    LayoutContentType.METRIC: "指标",
    LayoutContentType.CHART: "图表",
    LayoutContentType.TABLE: "表格",
    LayoutContentType.SHAPE: "形状",
}


def format_element_label(*, element_id: str, role: LayoutElementRole) -> str:
    role_label = ROLE_LABELS.get(role, role.value)
    return f"{role_label} · {element_id}"
