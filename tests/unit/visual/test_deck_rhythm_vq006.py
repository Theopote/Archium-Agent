"""VQ-006: Deck rhythm stamps must change the compiled picture."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.deck_rhythm import (
    apply_deck_rhythm_to_scene,
    resolve_page_rhythm,
    stamp_deck_rhythm_onto_intents,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.deck_composition import (
    DeckCompositionPlan,
    PacingRole,
    SlideCompositionDirective,
    VisualIntensity,
)
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.page_direction import NarrativeEmotion, PageDirection
from archium.domain.visual.render_scene import TextNode
from archium.domain.visual.visual_intent import VisualIntent


def _plan(slide_id, title: str = "更新策略") -> LayoutPlan:
    return LayoutPlan(
        slide_id=slide_id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="default",
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
                height=0.9,
                style_token="title",
            )
        ],
        reading_order=["title"],
    )


def test_climax_title_scales_above_pause() -> None:
    climax = resolve_page_rhythm(
        pacing_role=PacingRole.CLIMAX,
        visual_intensity=VisualIntensity.HERO,
        target_density=DensityLevel.SPACIOUS,
    )
    pause = resolve_page_rhythm(
        pacing_role=PacingRole.PAUSE,
        visual_intensity=VisualIntensity.LOW,
        target_density=DensityLevel.SPACIOUS,
    )
    assert climax.title_scale > pause.title_scale
    assert climax.quiet is False
    assert pause.quiet is True
    assert climax.motif_mark_bias > pause.motif_mark_bias


def test_apply_rhythm_quiets_motif_on_pause_pages() -> None:
    design = default_presentation_design_system()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=0,
        title="呼吸页",
        message="留白",
        slide_type=SlideType.CONTENT,
        key_points=["a"],
    )
    plan = _plan(slide.id, "呼吸页")
    plan = plan.model_copy(update={"design_system_id": design.id})
    scene = RenderSceneCompiler().compile(slide=slide, layout_plan=plan, design_system=design)
    # Inject synthetic motif nodes so quieting is observable without PATH concept.
    from archium.domain.visual.render_scene import ShapeNode

    scene = scene.model_copy(
        update={
            "nodes": [
                *list(scene.nodes),
                ShapeNode(
                    id="vl_motif_node_0",
                    semantic_role="graphic_motif",
                    x=1,
                    y=1,
                    width=0.2,
                    height=0.2,
                    z_index=4,
                    opacity=0.9,
                    shape_kind="ellipse",
                    fill_color="#C45C26",
                    stroke_color="#C45C26",
                    stroke_width=1,
                ),
                ShapeNode(
                    id="vl_motif_connector_0",
                    semantic_role="graphic_motif_connector",
                    x=1,
                    y=1,
                    width=2,
                    height=0.1,
                    z_index=3,
                    opacity=0.8,
                    shape_kind="rectangle",
                    fill_color="#C45C26",
                    stroke_color="#C45C26",
                    stroke_width=0,
                ),
            ]
        }
    )
    stamp = resolve_page_rhythm(pacing_role=PacingRole.PAUSE)
    quieted = apply_deck_rhythm_to_scene(scene, stamp)
    motif_ids = [n.id for n in quieted.nodes if str(getattr(n, "id", "")).startswith("vl_motif_")]
    assert "vl_motif_connector_0" not in motif_ids
    assert "vl_motif_node_0" not in motif_ids
    assert "deck_rhythm:pause" in quieted.warnings
    assert "deck_rhythm:quiet" in quieted.warnings


def test_compile_honors_stamped_pacing_on_page_direction() -> None:
    design = default_presentation_design_system()
    presentation_id = uuid4()
    slide = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="demo",
        order=0,
        title="概念高潮",
        message="决定性一页",
        slide_type=SlideType.CONTENT,
        key_points=["概念"],
    )
    direction = PageDirection(
        single_message="概念高潮",
        narrative_emotion=NarrativeEmotion.CLIMAX,
        pacing_role=PacingRole.CLIMAX.value,
        visual_intensity=VisualIntensity.HERO.value,
        background_mode="accent_wash",
    )
    intent = VisualIntent(
        slide_id=slide.id,
        presentation_id=presentation_id,
        communication_goal="高潮",
        audience_takeaway="记住概念",
        visual_priority="title > visual",
        dominant_content_type=VisualContentType.HERO_IMAGE,
        preferred_layout_families=[LayoutFamily.HERO],
        density_level=DensityLevel.SPACIOUS,
        continuity_role=ContinuityRole.CLIMAX,
        page_direction=direction,
    )
    plan = _plan(slide.id, "概念高潮")
    plan = plan.model_copy(
        update={"design_system_id": design.id, "visual_intent_id": intent.id}
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        visual_intent=intent,
    )
    title = next(n for n in scene.nodes if isinstance(n, TextNode) and n.semantic_role == "title")
    assert "deck_rhythm:climax" in scene.warnings
    # Grammar + climax rhythm should push title well above the default ~28–36pt band.
    assert title.font_size >= 36


def test_stamp_deck_rhythm_writes_pacing_onto_intents() -> None:
    presentation_id = uuid4()
    slide_id = uuid4()
    intent = VisualIntent(
        slide_id=slide_id,
        presentation_id=presentation_id,
        communication_goal="证据",
        audience_takeaway="看清冲突",
        visual_priority="drawing > title",
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
        density_level=DensityLevel.COMPACT,
        continuity_role=ContinuityRole.EVIDENCE,
        page_direction=PageDirection(
            single_message="现状冲突",
            narrative_emotion=NarrativeEmotion.PROBLEM,
        ),
    )
    plan = DeckCompositionPlan(
        presentation_id=presentation_id,
        art_direction_id=uuid4(),
        composition_strategy="test",
        pacing_strategy="test",
        slide_directives=[
            SlideCompositionDirective(
                slide_id=slide_id,
                slide_index=0,
                narrative_role="evidence",
                pacing_role=PacingRole.EVIDENCE,
                visual_intensity=VisualIntensity.HIGH,
                target_density=DensityLevel.COMPACT,
                preferred_layout_families=[LayoutFamily.EVIDENCE_BOARD],
                background_mode="light",
                should_contrast_previous=True,
            )
        ],
    )
    stamped = stamp_deck_rhythm_onto_intents(deck_plan=plan, intents=[intent])
    direction = stamped[0].page_direction
    assert direction.pacing_role == "evidence"
    assert direction.visual_intensity == "high"
    assert direction.background_mode == "light"
    assert direction.should_contrast_previous is True
    assert direction.density_override == DensityLevel.COMPACT
    assert any(str(e).startswith("deck_pacing:") for e in direction.evidence)
