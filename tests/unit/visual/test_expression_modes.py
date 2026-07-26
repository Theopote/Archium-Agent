"""Expression Mode registry + locked layout contracts (v0.3 Phase 2)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.visual_grammar_intent import preferred_variant_for_intent
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, SlideVisualRequirement
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.expression_mode import (
    ExpressionModeId,
    get_expression_mode,
    list_expression_modes,
    recognize_expression_mode,
)
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.layout.layout_solver import LayoutSolver
from archium.domain.visual.defaults import default_presentation_design_system


# Fixture copy for each mode — titles/messages tuned for recognition.
_MODE_FIXTURES: dict[ExpressionModeId, dict[str, object]] = {
    ExpressionModeId.HERO_OPENING: {
        "title": "封面开篇",
        "message": "院落重生：一句概念宣言。",
        "key_points": [],
        "archetype": PageArchetype.NARRATIVE_OPENING,
    },
    ExpressionModeId.PROBLEM_TO_SOLUTION: {
        "title": "现状问题诊断",
        "message": "入口混乱与候诊过长形成核心矛盾，因此需要策略回应。",
        "key_points": ["入口", "候诊", "问询"],
        "archetype": PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    },
    ExpressionModeId.DRAWING_STORY: {
        "title": "总平面布局",
        "message": "总平面确立院落轴线与核心公服节点。",
        "key_points": ["轴线", "编号图注", "入口"],
        "archetype": PageArchetype.SITE_CONTEXT_ANALYSIS,
    },
    ExpressionModeId.BEFORE_AFTER: {
        "title": "改造前后对比",
        "message": "Before / After 呈现空间提升与流线改善。",
        "key_points": ["变化", "提升"],
        "archetype": PageArchetype.BEFORE_AFTER_TRANSFORMATION,
    },
    ExpressionModeId.EVIDENCE_BOARD: {
        "title": "现场证据踏勘",
        "message": "现场照片编号对应问题点，结论条收束。",
        "key_points": ["照片1", "照片2", "照片3", "照片4"],
        "archetype": PageArchetype.SITE_PROBLEM_DIAGNOSIS,
    },
    ExpressionModeId.ANALYTICAL_DIAGRAM: {
        "title": "流线分析图",
        "message": "分析图叠加关系图层，callout 服务读图。",
        "key_points": ["主轴", "次轴", "节点"],
        "archetype": None,
    },
    ExpressionModeId.STRATEGY_CARDS: {
        "title": "设计策略",
        "message": "三大策略原则：分流、院落、可识别。",
        "key_points": ["策略一", "策略二", "策略三"],
        "archetype": PageArchetype.DESIGN_STRATEGY,
    },
    ExpressionModeId.PROCESS_NARRATIVE: {
        "title": "分期实施流程",
        "message": "一期启动、二期置换、三期完善。",
        "key_points": ["一期", "二期", "三期", "四期"],
        "archetype": None,
    },
    ExpressionModeId.METRIC_DASHBOARD: {
        "title": "关键指标对标",
        "message": "绿地率提升 12%，步行距离下降 30%。",
        "key_points": ["绿地率", "步行距离", "床位", "候诊"],
        "archetype": None,
    },
    ExpressionModeId.HYBRID_CLIMAX: {
        "title": "综合效果呈现",
        "message": "最终综合表达院落重生愿景。",
        "key_points": ["高潮视觉", "一句结论"],
        "archetype": None,
    },
}


def test_registry_has_exactly_ten_modes() -> None:
    modes = list_expression_modes()
    assert len(modes) == 10
    assert {m.id for m in modes} == set(ExpressionModeId)


@pytest.mark.parametrize("mode_id", list(ExpressionModeId))
def test_each_mode_locks_implemented_family_and_variant(mode_id: ExpressionModeId) -> None:
    mode = get_expression_mode(mode_id)
    registry = get_layout_family_registry()
    definition = registry.get(mode.primary_family)
    assert definition is not None
    assert definition.implemented
    assert mode.primary_variant in definition.supported_variants
    assert mode.copy_budget.max_key_points <= 5
    assert len(mode.human_checklist) >= 2


@pytest.mark.parametrize("mode_id", list(ExpressionModeId))
def test_recognize_and_direct_locks_variant(mode_id: ExpressionModeId) -> None:
    fixture = _MODE_FIXTURES[mode_id]
    mode = get_expression_mode(mode_id)
    recognized = recognize_expression_mode(
        title=str(fixture["title"]),
        message=str(fixture["message"]),
        key_points=list(fixture["key_points"]),  # type: ignore[arg-type]
        page_archetype=fixture["archetype"],  # type: ignore[arg-type]
    )
    assert recognized is not None
    assert recognized.id == mode_id

    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="body",
        order=1,
        title=str(fixture["title"]),
        message=str(fixture["message"]),
        key_points=list(fixture["key_points"]),  # type: ignore[arg-type]
    )
    direction = PageDirectionService().direct(
        slide,
        page_archetype=fixture["archetype"],  # type: ignore[arg-type]
    )
    assert direction.expression_mode_id == mode_id.value
    assert direction.locked_layout_variant == mode.primary_variant
    assert direction.preferred_layout_families[0] == mode.primary_family
    assert direction.copy_budget.max_key_points <= mode.copy_budget.max_key_points + 1


@pytest.mark.parametrize("mode_id", list(ExpressionModeId))
def test_mode_generates_locked_layout_plan(mode_id: ExpressionModeId) -> None:
    mode = get_expression_mode(mode_id)
    fixture = _MODE_FIXTURES[mode_id]
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="body",
        order=2,
        title=str(fixture["title"]),
        message=str(fixture["message"]),
        key_points=list(fixture["key_points"]) or ["要点"],  # type: ignore[arg-type]
        visual_requirements=[
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="visual",
                preferred_asset_ids=[uuid4()],
            ),
            SlideVisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="visual-2",
                preferred_asset_ids=[uuid4()],
            ),
        ],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="表达模式验证",
        audience_takeaway=slide.message,
        visual_priority="mode lock",
        dominant_content_type=VisualContentType.MIXED,
        preferred_layout_families=[mode.primary_family],
        preferred_layout_variant=mode.primary_variant,
        expression_mode_id=mode.id.value,
        density_level=mode.density,
        page_archetype=fixture["archetype"],  # type: ignore[arg-type]
        hero_asset_id=slide.visual_requirements[0].preferred_asset_ids[0],
        supporting_asset_ids=[slide.visual_requirements[1].preferred_asset_ids[0]],
    )
    assert preferred_variant_for_intent(intent, mode.primary_family) == mode.primary_variant

    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=list(slide.key_points),
        metrics=list(slide.key_points)[:4],
        hero_asset_ref=str(intent.hero_asset_id),
        supporting_asset_refs=[str(aid) for aid in intent.supporting_asset_ids],
        case_labels=["before", "after"],
        insight=slide.message,
    )
    plan = LayoutSolver().generate(
        mode.primary_family,
        LayoutGeneratorContext(
            slide=slide,
            visual_intent=intent,
            art_direction=None,
            design_system=default_presentation_design_system(),
            content=content,
            variant=mode.primary_variant,
        ),
    )
    assert plan.layout_family == mode.primary_family
    assert plan.layout_variant == mode.primary_variant
    assert plan.element_by_id("title") is not None or plan.elements


def test_problem_to_solution_pair_roles() -> None:
    problem = get_expression_mode(ExpressionModeId.PROBLEM_TO_SOLUTION)
    solution = get_expression_mode(ExpressionModeId.STRATEGY_CARDS)
    assert problem.pair_role.value == "problem"
    assert solution.pair_role.value == "solution"
    assert problem.primary_family == LayoutFamily.EVIDENCE_BOARD
    assert solution.primary_family == LayoutFamily.STRATEGY_CARDS


def test_hero_opening_forbids_text_heap() -> None:
    mode = get_expression_mode(ExpressionModeId.HERO_OPENING)
    assert mode.copy_budget.max_key_points == 0
    assert LayoutFamily.TEXTUAL_ARGUMENT in mode.forbidden_families
