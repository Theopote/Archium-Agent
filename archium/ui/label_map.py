"""User-facing labels for domain terms in Presentation Studio."""

from __future__ import annotations

ENTITY_LABELS: dict[str, str] = {
    "SlideSpec": "页面内容",
    "LayoutPlan": "页面版式",
    "VisualIntent": "页面视觉意图",
    "ArtDirection": "视觉方向",
    "DesignSystem": "设计规范",
    "PresentationBrief": "汇报简报",
    "Storyline": "叙事结构",
    "DeckCompositionPlan": "整套节奏规划",
    "Deck QA": "整套一致性",
    "Visual Critic": "视觉质量评估",
    "LayoutFamily": "版式类型",
    "LayoutElement": "版式元素",
    "AssetBoard": "素材板",
    "Citation": "引用来源",
}

FIELD_LABELS: dict[str, str] = {
    "title": "标题",
    "message": "核心信息",
    "communication_goal": "沟通目标",
    "audience_takeaway": "受众带走",
    "visual_priority": "视觉优先级",
    "dominant_content_type": "主导内容",
    "density_level": "信息密度",
    "continuity_role": "连续角色",
    "layout_family": "版式类型",
    "layout_variant": "版式变体",
    "whitespace_ratio": "留白比例",
    "validation_status": "校验状态",
    "reading_order": "阅读顺序",
}

STATUS_LABELS: dict[str, str] = {
    "ready": "可导出",
    "needs_visual": "待生成版式",
    "needs_review": "待审核",
    "has_issues": "有问题",
    "empty": "暂无页面",
}


def entity_label(name: str, *, advanced: bool = False) -> str:
    """Return user-facing entity name unless advanced mode is enabled."""
    if advanced:
        return name
    return ENTITY_LABELS.get(name, name)


def field_label(name: str, *, advanced: bool = False) -> str:
    """Return user-facing field name unless advanced mode is enabled."""
    if advanced:
        return name
    return FIELD_LABELS.get(name, name)
