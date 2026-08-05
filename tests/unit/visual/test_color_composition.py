"""Unit tests for VQ-002 Project Color Composition."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.color_composition import (
    apply_color_composition_to_scene,
    compose_color_composition,
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
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.visual_language.color_composition import BackgroundMode


def _slide(*, title: str, slide_type: SlideType = SlideType.CONTENT) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=0,
        title=title,
        message="takeaway",
        slide_type=slide_type,
        key_points=["要点"],
    )


def _plan(*, family: LayoutFamily = LayoutFamily.HERO, title: str = "封面") -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=family,
        layout_variant="full_bleed",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=title,
                x=0.5,
                y=0.4,
                width=9,
                height=1.0,
                style_token="display",
            )
        ],
        reading_order=["title"],
    )


def test_cover_uses_dark_background_mode() -> None:
    design = default_presentation_design_system()
    composition = compose_color_composition(
        design_system=design,
        slide=_slide(title="封面", slide_type=SlideType.TITLE),
    )
    assert composition.background_mode == BackgroundMode.DARK
    assert composition.background_hex == design.colors.resolve("primary")
    assert composition.primary_text_hex == design.colors.resolve("surface")
    assert composition.accent_ratio <= 0.12


def test_evidence_family_prefers_light_board() -> None:
    design = default_presentation_design_system()
    composition = compose_color_composition(
        design_system=design,
        slide=_slide(title="现场证据"),
        layout_plan=_plan(family=LayoutFamily.EVIDENCE_BOARD, title="现场证据"),
        visual_intent=VisualIntent(
            slide_id=uuid4(),
            communication_goal="evidence",
            audience_takeaway="问题可见",
            visual_priority="photos",
            dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
            continuity_role=ContinuityRole.EVIDENCE,
        ),
    )
    assert composition.background_mode == BackgroundMode.LIGHT
    assert composition.background_hex is not None
    assert composition.background_hex.upper() != design.colors.resolve("primary").upper()


def test_climax_raises_accent_ratio_and_wash() -> None:
    design = default_presentation_design_system()
    direction = PageDirection(
        single_message="高潮主张",
        narrative_emotion=NarrativeEmotion.CLIMAX,
        must_show=["hero"],
        must_hide=["bullet_wall"],
    )
    composition = compose_color_composition(
        design_system=design,
        slide=_slide(title="核心理念"),
        page_direction=direction,
    )
    assert composition.background_mode in {
        BackgroundMode.ACCENT_WASH,
        BackgroundMode.TINTED,
    }
    assert composition.accent_ratio >= 0.08


def test_visual_language_spec_includes_color_composition() -> None:
    slide = _slide(title="封面", slide_type=SlideType.TITLE)
    direction = PageDirection(
        single_message="封面主张",
        narrative_emotion=NarrativeEmotion.CALM,
        must_show=["hero"],
        must_hide=[],
    )
    language = VisualLanguageService().compose(slide, direction)
    assert language.color_composition is not None
    assert language.color_composition.background_mode == BackgroundMode.DARK
    assert "配 `" in language.summary_caption()


def test_compiler_darkens_cover_and_adds_accent_edge() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="更新不是修补", slide_type=SlideType.TITLE)
    plan = _plan(title="更新不是修补")
    plan = plan.model_copy(update={"slide_id": slide.id})
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="cover",
        audience_takeaway="主张",
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
    assert scene.background.color == design.colors.resolve("primary")
    title = next(n for n in scene.nodes if isinstance(n, TextNode) and n.id == "title")
    assert title.color.upper() == design.colors.resolve("surface").upper()
    edge = next(
        (
            n
            for n in scene.nodes
            if isinstance(n, ShapeNode) and n.semantic_role == "color_composition_edge"
        ),
        None,
    )
    assert edge is not None
    assert any(w.startswith("color_composition:dark") for w in scene.warnings)


def test_apply_color_composition_idempotent_via_strip() -> None:
    """Re-applying should replace prior wash/edge nodes, not stack forever."""
    from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ThemeTokens

    design = default_presentation_design_system()
    composition = compose_color_composition(
        design_system=design,
        slide=_slide(title="封面", slide_type=SlideType.TITLE),
    )
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[],
        theme_tokens=ThemeTokens(colors={"background": "#FFFFFF"}),
        warnings=[],
    )
    once = apply_color_composition_to_scene(scene, composition)
    twice = apply_color_composition_to_scene(once, composition)
    edges_once = [n for n in once.nodes if getattr(n, "id", "").startswith("color_accent")]
    edges_twice = [n for n in twice.nodes if getattr(n, "id", "").startswith("color_accent")]
    assert len(edges_once) == 1
    assert len(edges_twice) == 1
