"""Unit tests for Architectural Visual Grammar (VG-001)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.visual_grammar_intent import (
    apply_grammar_to_draft,
    derive_grammar_layout_preference,
    forbidden_families_for_intent,
)
from archium.application.visual.visual_grammar_recognition import recognize_page_archetype
from archium.domain.enums import SlideType, VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.visual.enums import (
    ContinuityRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.visual_grammar import PageArchetype, get_recipe
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.llm.visual_schemas import VisualIntentDraft


def _slide(
    *,
    title: str,
    message: str = "说明文字。",
    key_points: list[str] | None = None,
    slide_type: SlideType = SlideType.CONTENT,
    visual_requirements: list[SlideVisualRequirement] | None = None,
) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title=title,
        message=message,
        slide_type=slide_type,
        key_points=key_points or [],
        visual_requirements=visual_requirements or [],
    )


def test_recognize_site_context_analysis() -> None:
    slide = _slide(
        title="区位与交通分析",
        message="基地位于城市副中心，地铁与主干道可达。",
        key_points=["地图展示周边交通", "尺度关系说明"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.MAP, description="区位地图"),
        ],
    )
    result = recognize_page_archetype(slide)
    assert result.archetype == PageArchetype.SITE_CONTEXT_ANALYSIS
    assert result.confidence >= 2.0
    assert any("区位" in item or "交通" in item or "map" in item for item in result.evidence)


def test_recognize_site_problem_diagnosis() -> None:
    slide = _slide(
        title="现状问题诊断",
        message="现场存在结构老化与空间不足等问题。",
        key_points=["问题1：结构", "问题2：空间"],
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.SITE_PHOTO, description="现场照片"),
        ],
    )
    result = recognize_page_archetype(slide)
    assert result.archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS
    assert result.recipe.dominant_content_type == VisualContentType.PHOTO_EVIDENCE


def test_recognize_design_strategy() -> None:
    slide = _slide(
        title="设计策略与原则",
        message="以开放公共空间串联历史肌理与现代功能。",
        key_points=["策略一", "策略二"],
    )
    result = recognize_page_archetype(slide)
    assert result.archetype == PageArchetype.DESIGN_STRATEGY
    assert LayoutFamily.STRATEGY_CARDS in result.recipe.preferred_layout_families


def test_recognize_before_after() -> None:
    slide = _slide(
        title="改造前后对比",
        message="改造后公共空间品质显著提升。",
        slide_type=SlideType.COMPARISON,
        visual_requirements=[
            SlideVisualRequirement(type=VisualType.COMPARISON, description="前后对照"),
        ],
    )
    result = recognize_page_archetype(slide)
    assert result.archetype == PageArchetype.BEFORE_AFTER_TRANSFORMATION
    assert (
        LayoutFamily.COMPARATIVE_MATRIX,
        "before_after",
    ) in result.recipe.preferred_variants


def test_recognize_generic_when_signals_weak() -> None:
    slide = _slide(title="附录", message="补充说明。")
    result = recognize_page_archetype(slide)
    assert result.archetype == PageArchetype.GENERIC
    assert result.confidence == 0.0


def test_apply_grammar_to_draft_sets_composition_strategy() -> None:
    recipe = get_recipe(PageArchetype.SITE_PROBLEM_DIAGNOSIS)
    draft = VisualIntentDraft(
        communication_goal="old",
        audience_takeaway="old",
        visual_priority="title > body",
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT],
        composition_strategy="generic",
    )
    updated = apply_grammar_to_draft(draft, recipe)
    assert updated.dominant_content_type == VisualContentType.PHOTO_EVIDENCE
    assert updated.preferred_layout_families[0] == LayoutFamily.EVIDENCE_BOARD
    assert "现场照片" in updated.composition_strategy
    assert updated.continuity_role == ContinuityRole.EVIDENCE


def test_derive_grammar_layout_preference_ranks_variants() -> None:
    intent = VisualIntent(
        slide_id=uuid4(),
        page_archetype=PageArchetype.BEFORE_AFTER_TRANSFORMATION,
        communication_goal="对比",
        audience_takeaway="变化",
        visual_priority="cases",
        dominant_content_type=VisualContentType.COMPARISON,
        preferred_layout_families=[LayoutFamily.COMPARATIVE_MATRIX],
        composition_strategy="Before / After",
    )
    pref = derive_grammar_layout_preference(intent)
    assert pref.preferred_families[0] == LayoutFamily.COMPARATIVE_MATRIX
    assert (LayoutFamily.COMPARATIVE_MATRIX, "before_after") in pref.preferred_variants
    assert any(note.startswith("visual_grammar:") for note in pref.notes)


def test_order_variants_for_intent_prioritizes_grammar() -> None:
    from archium.application.visual.visual_grammar_intent import order_variants_for_intent

    intent = VisualIntent(
        slide_id=uuid4(),
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        communication_goal="诊断",
        audience_takeaway="问题",
        visual_priority="photos",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
    )
    ordered = order_variants_for_intent(
        intent,
        LayoutFamily.EVIDENCE_BOARD,
        ("photo_grid", "numbered_grid", "diagnosis_split"),
    )
    assert ordered[0] == "diagnosis_split"


def test_rule_decisions_respects_grammar_forbidden_families() -> None:
    from archium.application.visual.layout_planning_service import LayoutPlanningService
    from archium.config.settings import get_settings

    intent = VisualIntent(
        slide_id=uuid4(),
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        communication_goal="展示现场证据",
        audience_takeaway="问题清晰",
        visual_priority="photos",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
        composition_strategy="左：现场照片；右：问题标签",
    )
    service = LayoutPlanningService.__new__(LayoutPlanningService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._validator = None  # noqa: SLF001
    service._solver = None  # noqa: SLF001
    from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry

    service._registry = get_layout_family_registry()  # noqa: SLF001
    service._plans = None  # noqa: SLF001
    service._intents = None  # noqa: SLF001
    service._art = None  # noqa: SLF001
    service._design = None  # noqa: SLF001
    service._settings = get_settings()  # noqa: SLF001
    service._warnings = []  # noqa: SLF001

    decisions = service._rule_decisions(intent, asset_count=3, candidate_count=5)  # noqa: SLF001
    families = {item.layout_family for item in decisions}
    assert LayoutFamily.HERO.value not in families
    assert LayoutFamily.STRATEGY_CARDS.value not in families
    assert LayoutFamily.EVIDENCE_BOARD.value in families
