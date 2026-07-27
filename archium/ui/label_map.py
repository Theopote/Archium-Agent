"""User-facing labels for domain terms across Archium UI."""

from __future__ import annotations

from archium.domain.slide_role import SlideRole

ENTITY_LABELS: dict[str, str] = {
    "ProjectMission": "我们对任务的理解",
    "KnowledgeGap": "还需要确认的信息",
    "DeliverablePlan": "计划生成的成果",
    "PresentationBrief": "汇报要求",
    "Storyline": "汇报结构",
    "OutlinePlan": "汇报大纲",
    "SlideSpec": "页面内容",
    "ArtDirection": "视觉方向",
    "VisualIntent": "本页表达重点",
    "LayoutPlan": "页面版式",
    "LayoutFamily": "版式类型",
    "LayoutElement": "版式元素",
    "ValidationIssue": "页面问题",
    "Visual Critic": "视觉检查",
    "Deck QA": "整套一致性检查",
    "ArchitectureSlideSemanticQA": "页面语义检查",
    "WorkflowRun": "生成任务",
    "Revision": "历史版本",
    "DesignSystem": "设计规范",
    "DeckCompositionPlan": "整套节奏规划",
    "AssetBoard": "素材板",
    "Citation": "引用来源",
    "PresentationSpec": "导出规格",
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

SLIDE_ROLE_LABELS: dict[SlideRole, str] = {
    SlideRole.OPENING: "封面 / 开篇",
    SlideRole.BACKGROUND: "背景",
    SlideRole.QUESTION: "问题提出",
    SlideRole.VISION: "愿景",
    SlideRole.CONCLUSION: "结论 / 收尾",
    SlideRole.SITE_ANALYSIS: "基地分析",
    SlideRole.CONTEXT_ANALYSIS: "语境分析",
    SlideRole.PROBLEM_ANALYSIS: "问题分析",
    SlideRole.CONCEPT: "概念",
    SlideRole.STRATEGY: "策略",
    SlideRole.SPATIAL_LOGIC: "空间逻辑",
    SlideRole.FORM: "形态",
    SlideRole.MATERIAL: "材料",
    SlideRole.EXPERIENCE: "体验",
    SlideRole.CASE_STUDY: "案例",
    SlideRole.COMPARISON: "对比",
    SlideRole.DATA: "数据",
    SlideRole.SUMMARY: "总结",
    SlideRole.TIMELINE: "时间线",
    SlideRole.IMPLEMENTATION: "实施",
    SlideRole.OTHER: "其他",
}


def slide_role_label(role: SlideRole | None, *, advanced: bool = False) -> str:
    """Architect-facing page role label."""
    if role is None:
        return "未标注"
    if advanced:
        return role.value
    return SLIDE_ROLE_LABELS.get(role, role.value.replace("_", " "))


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


def content_pipeline_chain(*, advanced: bool = False) -> str:
    """User-facing label for Brief → Storyline → SlideSpec pipeline."""
    return " → ".join(
        [
            entity_label("PresentationBrief", advanced=advanced),
            entity_label("Storyline", advanced=advanced),
            entity_label("SlideSpec", advanced=advanced),
        ]
    )


def product_flow_chain() -> str:
    """Primary product stages: 资料 → 大纲 → 生成 → 编辑 → 交付."""
    from archium.ui.product_flow import product_flow_chain as _chain

    return _chain()


def brief_storyline_pair(*, advanced: bool = False) -> str:
    """User-facing label for Brief + Storyline pair."""
    return f"{entity_label('PresentationBrief', advanced=advanced)} / {entity_label('Storyline', advanced=advanced)}"


def visual_pipeline_chain(*, advanced: bool = False) -> str:
    """User-facing label for ArtDirection → VisualIntent → LayoutPlan pipeline."""
    return " → ".join(
        [
            entity_label("ArtDirection", advanced=advanced),
            entity_label("VisualIntent", advanced=advanced),
            entity_label("LayoutPlan", advanced=advanced),
        ]
    )


def visual_quality_pair(*, advanced: bool = False) -> str:
    """User-facing label for Visual Critic + Deck QA."""
    return (
        f"{entity_label('Visual Critic', advanced=advanced)} / "
        f"{entity_label('Deck QA', advanced=advanced)}"
    )


def revision_history_label(entity: str, *, advanced: bool = False) -> str:
    """User-facing revision history title for an entity."""
    return f"{entity_label(entity, advanced=advanced)}{entity_label('Revision', advanced=advanced)}"


def regenerate_label(entity: str, *, advanced: bool = False) -> str:
    """User-facing regenerate action label."""
    return f"重新生成{entity_label(entity, advanced=advanced)}"


def regenerate_success_label(entity: str, *, advanced: bool = False) -> str:
    """User-facing regenerate success message."""
    return f"{entity_label(entity, advanced=advanced)}已重新生成。"


def regenerate_failure_label(entity: str, *, advanced: bool = False) -> str:
    """User-facing regenerate failure message."""
    return f"重新生成{entity_label(entity, advanced=advanced)}失败：{{error}}"
