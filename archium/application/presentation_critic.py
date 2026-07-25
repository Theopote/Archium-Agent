"""PresentationCritic — deck-level narrative / visual / architecture critique.

Critic seat artifact. Aggregates existing signals; does not rewrite the deck.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole


class PresentationCritiqueReport(DomainModel):
    """Aggregated deck critique scores and actionable suggestions."""

    story_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    visual_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    architectural_expression: float = Field(default=0.5, ge=0.0, le=1.0)
    missing_points: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    overloaded_slides: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def critique_presentation(
    *,
    brief: PresentationBrief | None = None,
    storyline: Storyline | None = None,
    slides: list[SlideSpec] | None = None,
) -> PresentationCritiqueReport:
    """Deterministic presentation critique (no LLM, no new Agent)."""
    slides = list(slides or [])
    missing: list[str] = []
    suggestions: list[str] = []
    overloaded: list[str] = []

    story = 0.55
    if storyline is not None and storyline.thesis.strip():
        story += 0.15
    if storyline is not None and storyline.chapters:
        story += min(0.15, 0.03 * len(storyline.chapters))
    if storyline is not None and storyline.narrative_arc is not None:
        story += 0.1
    if brief is not None and brief.presentation_intent is not None:
        intent = brief.presentation_intent
        if intent.persuasion_strategy.strip():
            story += 0.05
        else:
            missing.append("缺少说服策略（PresentationIntent.persuasion_strategy）")
    elif brief is not None:
        missing.append("Brief 未挂 PresentationIntent，受众说服策略不清晰")

    if storyline is not None and not storyline.chapters:
        missing.append("Storyline 无章节")
        story -= 0.2

    visual = 0.5
    arch = 0.5
    role_hits = 0
    strategy_hits = 0
    analysis_roles = {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
    }
    analysis_with_strategy = 0
    analysis_total = 0

    for slide in slides:
        if len(slide.key_points) > 5 or len(slide.message) > 120:
            overloaded.append(f"{slide.title}（信息密度偏高）")
        if slide.slide_role is not None and slide.slide_role != SlideRole.OTHER:
            role_hits += 1
        if slide.visual_strategy is not None and not slide.visual_strategy.is_empty():
            strategy_hits += 1
        if slide.slide_role in analysis_roles:
            analysis_total += 1
            if slide.visual_strategy is not None and slide.visual_strategy.recommended_diagram.strip():
                analysis_with_strategy += 1

    if slides:
        visual += 0.2 * (role_hits / len(slides))
        visual += 0.2 * (strategy_hits / len(slides))
        if overloaded:
            visual -= min(0.2, 0.05 * len(overloaded))
            suggestions.append("压缩信息过载页：每页保留单一核心结论")
        if role_hits < len(slides) * 0.5:
            suggestions.append("补全 SlideRole，避免版式类型冒充页叙事角色")
        if strategy_hits < len(slides) * 0.4:
            suggestions.append("为关键页补 VisualStrategy（图解类型服务于论证）")

    if analysis_total:
        arch += 0.3 * (analysis_with_strategy / analysis_total)
        if analysis_with_strategy < analysis_total:
            missing.append("部分分析/策略页缺少推荐图解（应用流线/轴测/关系图而非装饰图）")
            suggestions.append("策略与问题页优先绑定分析图，效果图留给体验页")
    else:
        if slides:
            missing.append("未见问题/策略/空间逻辑类页角色，设计核心可能未展开")
            arch -= 0.1

    if brief is not None and brief.core_message.strip() and slides:
        core = brief.core_message.strip()[:24]
        if not any(core[:12] in (s.message + s.title) for s in slides[:8]):
            suggestions.append("检查首页或结论页是否回扣 Brief 核心信息")

    story = max(0.0, min(1.0, story))
    visual = max(0.0, min(1.0, visual))
    arch = max(0.0, min(1.0, arch))
    return PresentationCritiqueReport(
        story_strength=round(story, 2),
        visual_quality=round(visual, 2),
        architectural_expression=round(arch, 2),
        missing_points=missing[:8],
        suggestions=suggestions[:8],
        overloaded_slides=overloaded[:8],
    )
