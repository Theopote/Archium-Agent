"""Page visual grammar formulas + deepened narratives."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.visual_language_apply import apply_visual_language_to_plan
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.page_visual_grammar import (
    PageGrammarId,
    list_page_formulas,
    select_page_formula,
)
from archium.domain.visual.visual_concept import VisualMetaphor
from archium.domain.visual.visual_narrative import MotionDirection


def _slide(title: str, message: str, *, order: int = 0) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message=message,
        key_points=["要点"],
    )


def test_page_grammar_catalog_has_twenty_formulas() -> None:
    formulas = list_page_formulas()
    assert len(formulas) == 20
    ids = {f.id for f in formulas}
    assert PageGrammarId.PROBLEM_EVIDENCE_CONFLICT in ids
    assert PageGrammarId.PATH_EXPERIENCE in ids
    assert PageGrammarId.CORE_EXPANSION in ids
    assert PageGrammarId.QUIET_ARGUMENT in ids
    assert PageGrammarId.MONUMENT_IMAGE in ids
    assert PageGrammarId.BEFORE_AFTER_CUT in ids
    assert PageGrammarId.SECTION_OPENER in ids
    assert PageGrammarId.PHASING_TIMELINE in ids
    assert PageGrammarId.THRESHOLD_SEQUENCE in ids
    assert PageGrammarId.EVIDENCE_TRIPTYCH in ids
    assert PageGrammarId.AXONOMETRIC_CALLOUT in ids
    assert PageGrammarId.MASTERPLAN_FOCUS in ids
    assert PageGrammarId.PROGRAM_STACK in ids
    assert PageGrammarId.QUOTE_CITATION in ids


def test_phasing_and_threshold_title_selection() -> None:
    assert select_page_formula(emotion="strategy", title="实施分期").id == (
        PageGrammarId.PHASING_TIMELINE
    )
    assert select_page_formula(emotion="calm", title="入口序列").id == (
        PageGrammarId.THRESHOLD_SEQUENCE
    )
    assert select_page_formula(emotion="calm", title="策略篇").id == (
        PageGrammarId.SECTION_OPENER
    )
    assert select_page_formula(
        emotion="strategy",
        title="项目与背景",
        continuity_role="section_opening",
    ).id == PageGrammarId.SECTION_OPENER

def test_conflict_page_selects_path_experience_formula() -> None:
    slide = _slide("流线冲突", "医患流线交叉与洁污混行是当前最大安全风险。")
    direction = PageDirectionService().direct(slide)
    assert direction.page_grammar is not None
    assert direction.page_grammar.id == PageGrammarId.PATH_EXPERIENCE
    assert direction.page_grammar.semantic_slots == ["Path", "Node", "SpatialSequence"]
    card = direction.as_page_claim()
    assert card["page_grammar"]["id"] == "path_experience"


def test_site_page_gets_layered_site_concept_and_layer_formula() -> None:
    slide = _slide("区位与交通", "城市界面与急诊入口的交通压力集中在北侧。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert direction.visual_concept.visual_metaphor == VisualMetaphor.LAYERED_SITE
    assert direction.visual_concept.narrative is not None
    assert (
        direction.visual_concept.narrative.graphic_language.direction
        == MotionDirection.LAYERED
    )
    assert direction.page_grammar is not None
    assert direction.page_grammar.id == PageGrammarId.LAYER_ANALYSIS


def test_flow_optimize_gets_path_to_experience() -> None:
    slide = _slide("流线优化", "分流后急诊与物流各行其道。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert (
        direction.visual_concept.visual_metaphor == VisualMetaphor.PATH_TO_EXPERIENCE
    )
    assert direction.page_grammar is not None
    assert direction.page_grammar.id == PageGrammarId.PATH_EXPERIENCE


def test_concept_generation_gets_core_expansion_and_circle_mask() -> None:
    slide = _slide("概念生成", "从核心体量生长出开放院落。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert (
        direction.visual_concept.visual_metaphor == VisualMetaphor.CORE_TO_EXPANSION
    )
    assert direction.page_grammar is not None
    assert direction.page_grammar.id == PageGrammarId.CORE_EXPANSION
    assert direction.visual_language is not None
    assert direction.visual_language.image_mask.kind.value == "circle"


def test_conclusion_gets_quiet_argument() -> None:
    slide = _slide("结论建议", "分期实施并锁定流线安全底线。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_concept is not None
    assert direction.visual_concept.visual_metaphor == VisualMetaphor.QUIET_ARGUMENT
    assert direction.page_grammar is not None
    assert direction.page_grammar.id == PageGrammarId.QUIET_ARGUMENT


def test_formula_primitives_materialize_on_plan() -> None:
    slide = _slide("流线冲突", "医患流线交叉")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
    assert "flow_line" in language.primitive_ids or "circulation" in language.primitive_ids
    # Path-experience pages get contour atmosphere.
    assert language.atmosphere.kind.value == "contour"
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=13.333,
        page_height=7.5,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="流线冲突",
                x=0.8,
                y=0.5,
                width=6.0,
                height=0.5,
                style_token="title",
            )
        ],
        reading_order=["title"],
    )
    updated = apply_visual_language_to_plan(
        plan,
        language,
        page_order=5,
        visual_budget=direction.visual_budget,
    )
    ids = {el.id for el in updated.elements}
    assert any(i.startswith("vl_atm_") for i in ids)
    assert any(i.startswith("vl_prim_") for i in ids) or any(
        i.startswith("vl_symbol_") for i in ids
    )
    prim = next(
        (el for el in updated.elements if el.id.startswith("vl_prim_")),
        None,
    )
    if prim is not None and prim.content_type == LayoutContentType.IMAGE:
        assert prim.content_ref and prim.content_ref.startswith("icon:")


def test_site_layer_gets_cad_grid_atmosphere() -> None:
    slide = _slide("区位与交通", "城市界面与急诊入口的交通压力集中在北侧。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_language is not None
    assert direction.visual_language.atmosphere.kind.value == "cad_grid"
    assert "底 `cad_grid`" in direction.visual_language.summary_caption()


def test_select_page_formula_problem_emotion() -> None:
    formula = select_page_formula(emotion="problem", title="现状问题总览")
    assert formula.id == PageGrammarId.PROBLEM_EVIDENCE_CONFLICT


def test_conflict_gets_photo_plus_analysis_composition() -> None:
    slide = _slide("流线冲突", "医患流线交叉与洁污混行是当前最大安全风险。")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
    assert language.image_composition.mode.value == "photo_plus_analysis"
    assert any(
        line.kind.value == "conflict" for line in language.image_composition.analysis_lines
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=13.333,
        page_height=7.5,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=5.0,
                y=1.0,
                width=7.5,
                height=5.0,
            )
        ],
        reading_order=["hero"],
    )
    updated = apply_visual_language_to_plan(
        plan,
        language,
        page_order=5,
        visual_budget=direction.visual_budget,
    )
    ids = {el.id for el in updated.elements}
    assert any(i.startswith("vl_icp_line_") for i in ids)
    assert "图 `photo_plus_analysis`" in language.summary_caption()


def test_site_layer_gets_layered_base_composition() -> None:
    slide = _slide("区位与交通", "城市界面与急诊入口的交通压力集中在北侧。")
    direction = PageDirectionService().direct(slide)
    assert direction.visual_language is not None
    assert direction.visual_language.image_composition.mode.value == "layered_base"


def test_image_mask_stamps_hero_element() -> None:
    slide = _slide("效果表达", "更新后的城市界面与入院体验。")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
    assert language.image_mask.kind.value in {"gradient_fade", "none", "rounded"}
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=13.333,
        page_height=7.5,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=0.5,
                y=0.5,
                width=8.0,
                height=5.0,
            )
        ],
        reading_order=["hero"],
    )
    # Force gradient for apply test.
    from archium.domain.visual.visual_language.image_mask import ImageMaskKind, ImageMaskSpec

    language = language.model_copy(
        update={
            "image_mask": ImageMaskSpec(
                kind=ImageMaskKind.GRADIENT_FADE,
                corner_radius=0.1,
                edge_softness=0.4,
            )
        }
    )
    updated = apply_visual_language_to_plan(plan, language, page_order=17)
    hero = next(el for el in updated.elements if el.id == "hero")
    assert hero.image_mask == "gradient_fade"
    assert hero.corner_radius == 0.1
