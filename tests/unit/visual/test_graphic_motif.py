"""Unit tests for VQ-003 Architectural Graphic Motif + deck color rhythm."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.color_composition import plan_deck_color_modes
from archium.application.visual.deck_composition_service import DeckCompositionPlanningService
from archium.application.visual.graphic_motif import (
    compose_graphic_motif,
    merge_motif_into_primitives,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.visual_language_service import VisualLanguageService
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
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
from archium.domain.visual.render_scene import ShapeNode, TextNode
from archium.domain.visual.visual_concept import VisualMetaphor
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.visual_language.color_composition import BackgroundMode
from archium.domain.visual.visual_language.graphic_motif import MotifType


def _slide(*, title: str, order: int = 0, slide_type: SlideType = SlideType.CONTENT) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message="takeaway",
        slide_type=slide_type,
        key_points=["要点"],
    )


def _intent(slide: SlideSpec, *, continuity: ContinuityRole = ContinuityRole.EXPLANATION) -> VisualIntent:
    return VisualIntent(
        slide_id=slide.id,
        communication_goal="goal",
        audience_takeaway="takeaway",
        visual_priority="title",
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        continuity_role=continuity,
        preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT],
    )


def test_fragment_metaphor_selects_flow_nodes_motif() -> None:
    from archium.domain.visual.visual_concept import FRAGMENT_TO_NETWORK_CONCEPT

    motif = compose_graphic_motif(
        slide=_slide(title="流线冲突"),
        concept=FRAGMENT_TO_NETWORK_CONCEPT,
    )
    assert motif.motif_type == MotifType.FLOW_NODES
    assert "flow_line" in motif.shape_vocabulary
    assert motif.max_marks >= 3


def test_cover_defaults_to_quiet_rule() -> None:
    motif = compose_graphic_motif(slide=_slide(title="封面", slide_type=SlideType.TITLE))
    assert motif.motif_type == MotifType.QUIET_RULE
    assert motif.arrangement.value == "monumental_rule"
    merged = merge_motif_into_primitives(["hero_statement"], motif)
    assert "thin_rule" in merged
    assert "hero_statement" in merged


def test_section_uses_margin_axis_arrangement() -> None:
    motif = compose_graphic_motif(
        slide=_slide(title="现状问题", slide_type=SlideType.SECTION),
    )
    assert motif.motif_type == MotifType.AXIS_GRID
    assert motif.arrangement.value == "margin_axis"


def test_closing_uses_closing_silence() -> None:
    motif = compose_graphic_motif(
        slide=_slide(title="结语", slide_type=SlideType.CLOSING),
    )
    assert motif.motif_type == MotifType.QUIET_RULE
    assert motif.arrangement.value == "closing_silence"
    assert motif.max_marks == 1


def test_visual_language_includes_motif() -> None:
    slide = _slide(title="核心理念")
    direction = PageDirection(
        single_message="主张",
        narrative_emotion=NarrativeEmotion.CLIMAX,
        must_show=["hero"],
        must_hide=[],
    )
    language = VisualLanguageService().compose(slide, direction)
    assert language.graphic_motif is not None
    assert "母题 `" in language.summary_caption()


def test_compiler_emits_motif_geometry_on_cover() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="更新不是修补", slide_type=SlideType.TITLE)
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
                height=1.0,
                style_token="display",
            )
        ],
        reading_order=["title"],
    )
    intent = _intent(slide, continuity=ContinuityRole.OPENING)
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        visual_intent=intent,
    )
    motifs = [
        n
        for n in scene.nodes
        if isinstance(n, ShapeNode) and str(n.id).startswith("vl_motif_")
    ]
    assert motifs
    assert any(w.startswith("graphic_motif:") for w in scene.warnings)
    assert any(w.startswith("motif_arrangement:monumental_rule") for w in scene.warnings)
    title_rule = next((n for n in motifs if n.id == "vl_motif_title_rule"), None)
    assert title_rule is not None
    assert title_rule.width >= 4.0  # monumental: ~72% of title band
    assert any(isinstance(n, TextNode) and n.id == "title" for n in scene.nodes)


def test_deck_color_rhythm_softens_triple_dark() -> None:
    modes = [
        BackgroundMode.DARK,
        BackgroundMode.DARK,
        BackgroundMode.DARK,
        BackgroundMode.LIGHT,
    ]
    adjusted = plan_deck_color_modes(modes)
    assert adjusted[0] == BackgroundMode.DARK
    assert adjusted[2] == BackgroundMode.DARK
    assert adjusted[1] == BackgroundMode.TINTED


def test_deck_composition_stamps_background_mode() -> None:
    presentation_id = uuid4()
    slides = [
        _slide(title="封面", order=0, slide_type=SlideType.TITLE),
        _slide(title="证据", order=1),
        _slide(title="分析", order=2),
        _slide(title="结语", order=3, slide_type=SlideType.CLOSING),
    ]
    for slide in slides:
        slide.presentation_id = presentation_id
    intents = [
        _intent(slides[0], continuity=ContinuityRole.OPENING),
        _intent(slides[1], continuity=ContinuityRole.EVIDENCE),
        _intent(slides[2], continuity=ContinuityRole.EXPLANATION),
        _intent(slides[3], continuity=ContinuityRole.CLOSING),
    ]
    plan = DeckCompositionPlanningService().plan(
        presentation_id=presentation_id,
        art_direction_id=uuid4(),
        slides=slides,
        visual_intents=intents,
    )
    modes = [d.background_mode for d in plan.slide_directives]
    assert all(modes)
    assert modes[0] == BackgroundMode.DARK.value
    assert modes[-1] == BackgroundMode.DARK.value
    assert any("color_rhythm:" in rule for rule in plan.variety_rules)
