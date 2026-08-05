"""VQ-005 Architectural Visual Grammar Library tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.architectural_grammar import (
    apply_grammar_to_scene,
    select_architectural_grammar,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.visual_language_service import VisualLanguageService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_visual_grammar import (
    ArchitecturalGrammarId,
    list_architectural_grammars,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    ContinuityRole,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
from archium.domain.visual.page_visual_grammar import PageGrammarId
from archium.domain.visual.render_scene import TextNode
from archium.domain.visual.visual_intent import VisualIntent


def _slide(title: str, *, slide_type: SlideType = SlideType.CONTENT) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=0,
        title=title,
        message="主张",
        slide_type=slide_type,
        key_points=["要点"],
    )


def test_catalog_has_twelve_grammars_and_p0_showcase() -> None:
    all_g = list_architectural_grammars()
    p0 = list_architectural_grammars(p0_only=True)
    assert len(all_g) == 12
    assert len(p0) >= 5
    ids = {g.grammar_id for g in p0}
    assert ArchitecturalGrammarId.MONUMENTAL_STATEMENT in ids
    assert ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL in ids
    assert ArchitecturalGrammarId.ANALYTICAL_OVERLAY in ids
    assert ArchitecturalGrammarId.DRAWING_ATLAS in ids
    assert ArchitecturalGrammarId.METRIC_MONUMENT in ids
    assert ArchitecturalGrammarId.FINAL_VISION in ids


def test_select_cover_and_closing_grammars() -> None:
    cover = select_architectural_grammar(slide=_slide("封面", slide_type=SlideType.TITLE))
    assert cover.grammar_id == ArchitecturalGrammarId.MONUMENTAL_STATEMENT
    closing = select_architectural_grammar(slide=_slide("结语", slide_type=SlideType.CLOSING))
    assert closing.grammar_id == ArchitecturalGrammarId.FINAL_VISION
    metric = select_architectural_grammar(slide=_slide("关键指标", slide_type=SlideType.DATA))
    assert metric.grammar_id == ArchitecturalGrammarId.METRIC_MONUMENT


def test_formula_maps_to_product_grammar() -> None:
    g = select_architectural_grammar(formula_id=PageGrammarId.LAYER_ANALYSIS)
    assert g.grammar_id == ArchitecturalGrammarId.ANALYTICAL_OVERLAY
    g2 = select_architectural_grammar(formula_id=PageGrammarId.DRAWING_DOMINANT)
    assert g2.grammar_id == ArchitecturalGrammarId.DRAWING_ATLAS


def test_language_compose_stamps_vq5_source() -> None:
    slide = _slide("封面", slide_type=SlideType.TITLE)
    direction = PageDirection(
        single_message="主张",
        narrative_emotion=NarrativeEmotion.CLIMAX,
        must_show=["hero"],
        must_hide=[],
    )
    language = VisualLanguageService().compose(slide, direction)
    assert language.source.startswith("vq5:")
    assert language.graphic_motif is not None
    stamped = VisualLanguageService().apply(direction, language, slide=slide)
    assert any(e.startswith("arch_grammar:") for e in stamped.evidence)
    assert stamped.background_mode is not None


def test_compiler_applies_monumental_title_boost() -> None:
    design = default_presentation_design_system()
    slide = _slide("更新不是修补", slide_type=SlideType.TITLE)
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="更新不是修补",
                x=0.55,
                y=0.4,
                width=8.9,
                height=1.2,
                style_token="display",
            )
        ],
        reading_order=["title"],
    )
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="cover",
        audience_takeaway="claim",
        visual_priority="title",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        continuity_role=ContinuityRole.OPENING,
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        visual_intent=intent,
    )
    assert any(w.startswith("arch_grammar:monumental_statement") for w in scene.warnings)
    assert any(w.startswith("vq5_p0:") for w in scene.warnings)
    title = next(n for n in scene.nodes if isinstance(n, TextNode) and n.id == "title")
    assert title.font_size >= 28
    assert title.runs  # typography composition still present


def test_apply_grammar_to_scene_is_idempotent() -> None:
    design = default_presentation_design_system()
    slide = _slide("封面", slide_type=SlideType.TITLE)
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="full_bleed",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="封面",
                x=0.5,
                y=0.4,
                width=9,
                height=1.0,
            )
        ],
        reading_order=["title"],
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    grammar = select_architectural_grammar(slide=slide)
    again = apply_grammar_to_scene(scene, grammar)
    assert again.warnings.count(f"arch_grammar:{grammar.grammar_id.value}") == 1
