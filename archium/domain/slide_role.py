"""SlideRole + VisualStrategy — page logic and visual reasoning contracts.

SlideRole unifies NarrativeStage / PageArchetype / SlideType into one product
vocabulary. VisualStrategy captures what the audience should *see*.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import NarrativeStage, SlideType
from archium.domain.visual.visual_grammar import (
    PageArchetype,
    get_recipe,
)


class SlideRole(StrEnum):
    """Architectural presentation page role (argument function, not layout chrome)."""

    OPENING = "opening"
    BACKGROUND = "background"
    QUESTION = "question"
    VISION = "vision"
    CONCLUSION = "conclusion"
    SITE_ANALYSIS = "site_analysis"
    CONTEXT_ANALYSIS = "context_analysis"
    PROBLEM_ANALYSIS = "problem_analysis"
    CONCEPT = "concept"
    STRATEGY = "strategy"
    SPATIAL_LOGIC = "spatial_logic"
    FORM = "form"
    MATERIAL = "material"
    EXPERIENCE = "experience"
    CASE_STUDY = "case_study"
    COMPARISON = "comparison"
    DATA = "data"
    SUMMARY = "summary"
    TIMELINE = "timeline"
    IMPLEMENTATION = "implementation"
    OTHER = "other"


class VisualStrategy(DomainModel):
    """What this page should make the audience see (not decorative filler)."""

    information_type: str = Field(default="", description="Dominant information kind.")
    recommended_diagram: str = Field(
        default="",
        description="Preferred diagram / drawing type.",
    )
    image_requirement: str = Field(
        default="",
        description="When / whether an image is required and what kind.",
    )
    graphic_language: str = Field(
        default="",
        description="Annotation / graphic language cue.",
    )

    def is_empty(self) -> bool:
        return not any(
            part.strip()
            for part in (
                self.information_type,
                self.recommended_diagram,
                self.image_requirement,
                self.graphic_language,
            )
        )

    def to_prompt_line(self) -> str:
        bits = []
        if self.information_type.strip():
            bits.append(f"信息：{self.information_type.strip()}")
        if self.recommended_diagram.strip():
            bits.append(f"图解：{self.recommended_diagram.strip()}")
        if self.image_requirement.strip():
            bits.append(f"图像：{self.image_requirement.strip()}")
        if self.graphic_language.strip():
            bits.append(f"图语：{self.graphic_language.strip()}")
        return " · ".join(bits)


_ARCHETYPE_TO_ROLE: dict[PageArchetype, SlideRole] = {
    PageArchetype.NARRATIVE_OPENING: SlideRole.OPENING,
    PageArchetype.SITE_CONTEXT_ANALYSIS: SlideRole.SITE_ANALYSIS,
    PageArchetype.SITE_PROBLEM_DIAGNOSIS: SlideRole.PROBLEM_ANALYSIS,
    PageArchetype.DESIGN_STRATEGY: SlideRole.STRATEGY,
    PageArchetype.BEFORE_AFTER_TRANSFORMATION: SlideRole.COMPARISON,
    PageArchetype.GENERIC: SlideRole.OTHER,
}

_STAGE_TO_ROLE: dict[NarrativeStage, SlideRole] = {
    NarrativeStage.CONTEXT: SlideRole.BACKGROUND,
    NarrativeStage.PROBLEM: SlideRole.PROBLEM_ANALYSIS,
    NarrativeStage.EVIDENCE: SlideRole.DATA,
    NarrativeStage.TENSION: SlideRole.QUESTION,
    NarrativeStage.STRATEGY: SlideRole.STRATEGY,
    NarrativeStage.RESOLUTION: SlideRole.SPATIAL_LOGIC,
    NarrativeStage.DECISION: SlideRole.CONCLUSION,
}

_SLIDE_TYPE_TO_ROLE: dict[SlideType, SlideRole] = {
    SlideType.TITLE: SlideRole.OPENING,
    SlideType.SECTION: SlideRole.BACKGROUND,
    SlideType.CONTENT: SlideRole.OTHER,
    SlideType.IMAGE: SlideRole.EXPERIENCE,
    SlideType.COMPARISON: SlideRole.COMPARISON,
    SlideType.TIMELINE: SlideRole.TIMELINE,
    SlideType.DATA: SlideRole.DATA,
    SlideType.SUMMARY: SlideRole.SUMMARY,
    SlideType.CLOSING: SlideRole.CONCLUSION,
}

_ROLE_DIAGRAM_HINTS: dict[SlideRole, str] = {
    SlideRole.OPENING: "概念氛围 / 标题关系图",
    SlideRole.BACKGROUND: "区位 / 语境图",
    SlideRole.QUESTION: "矛盾对照图",
    SlideRole.PROBLEM_ANALYSIS: "流线冲突图 / 问题叠加图 / 热力示意",
    SlideRole.SITE_ANALYSIS: "基地分析图 / 等高线 / 现状拼贴",
    SlideRole.CONTEXT_ANALYSIS: "城市关系 / 文脉图",
    SlideRole.STRATEGY: "策略轴测 / 空间组织图",
    SlideRole.SPATIAL_LOGIC: "剖面 / 空间关系图 / 动线",
    SlideRole.CONCEPT: "概念生成图解",
    SlideRole.COMPARISON: "前后对比 / 方案对照",
    SlideRole.EXPERIENCE: "人在空间中的场景",
    SlideRole.DATA: "数据图 / 指标对照",
    SlideRole.SUMMARY: "结论提纲图",
    SlideRole.CONCLUSION: "决策要点图",
    SlideRole.IMPLEMENTATION: "分期 / 实施路径图",
}


def slide_role_from_archetype(archetype: PageArchetype | None) -> SlideRole | None:
    if archetype is None:
        return None
    return _ARCHETYPE_TO_ROLE.get(archetype)


def slide_role_from_narrative_stage(stage: NarrativeStage | None) -> SlideRole | None:
    if stage is None:
        return None
    return _STAGE_TO_ROLE.get(stage)


def slide_role_from_slide_type(slide_type: SlideType | None) -> SlideRole | None:
    if slide_type is None:
        return None
    return _SLIDE_TYPE_TO_ROLE.get(slide_type)


def resolve_slide_role(
    *,
    page_archetype: PageArchetype | None = None,
    narrative_stage: NarrativeStage | None = None,
    slide_type: SlideType | None = None,
    existing: SlideRole | None = None,
) -> SlideRole:
    if existing is not None and existing != SlideRole.OTHER:
        return existing
    for candidate in (
        slide_role_from_archetype(page_archetype),
        slide_role_from_narrative_stage(narrative_stage),
        slide_role_from_slide_type(slide_type),
    ):
        if candidate is not None and candidate != SlideRole.OTHER:
            return candidate
    return existing or SlideRole.OTHER


def visual_strategy_from_role(
    role: SlideRole,
    *,
    page_archetype: PageArchetype | None = None,
) -> VisualStrategy:
    diagram = _ROLE_DIAGRAM_HINTS.get(role, "")
    information = ""
    image_req = ""
    graphic = ""
    if page_archetype is not None:
        recipe = get_recipe(page_archetype)
        information = getattr(recipe.dominant_content_type, "value", str(recipe.dominant_content_type))
        image_req = recipe.image_treatment
        graphic = recipe.annotation_strategy
        if recipe.composition_strategy.strip() and not diagram:
            diagram = recipe.composition_strategy.strip()
        if recipe.visual_type_hints and not diagram:
            diagram = "、".join(sorted(v.value for v in recipe.visual_type_hints)[:4])
    if role in {SlideRole.PROBLEM_ANALYSIS, SlideRole.SITE_ANALYSIS, SlideRole.STRATEGY} and not image_req:
        image_req = "优先项目证据图/分析图；避免纯装饰效果图"
    if role in {SlideRole.OPENING, SlideRole.EXPERIENCE, SlideRole.VISION} and not image_req:
        image_req = "可用示意性氛围图（非证据）"
    return VisualStrategy(
        information_type=information or role.value,
        recommended_diagram=diagram,
        image_requirement=image_req,
        graphic_language=graphic,
    )


def coerce_slide_role(value: object) -> SlideRole | None:
    if value is None or value == "":
        return None
    if isinstance(value, SlideRole):
        return value
    try:
        return SlideRole(str(value))
    except ValueError:
        return None
