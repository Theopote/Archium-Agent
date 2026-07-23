"""RenderScene compile contracts: overflow policy, empty text, aliases."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.render_scene_compiler import (
    RenderSceneCompiler,
    _scene_overflow_policy,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    OverflowPolicy,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import TextNode
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


def _plan_with_text(
    slide: SlideSpec,
    *,
    text: str,
    element_id: str = "body",
    overflow_policy: OverflowPolicy = OverflowPolicy.WARN,
) -> LayoutPlan:
    design = default_presentation_design_system()
    return LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="default",
        page_width=10.0,
        page_height=5.625,
        overflow_policy=overflow_policy,
        elements=[
            LayoutElement(
                id=element_id,
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                x=0.5,
                y=1.0,
                width=8.0,
                height=1.0,
                text_content=text,
            )
        ],
        design_system_id=design.id,
        visual_intent_id=uuid4(),
    )


def test_scene_overflow_policy_is_identity() -> None:
    assert _scene_overflow_policy(OverflowPolicy.WARN) == OverflowPolicy.WARN
    assert _scene_overflow_policy(OverflowPolicy.SPLIT) == OverflowPolicy.SPLIT
    assert _scene_overflow_policy(OverflowPolicy.SHRINK) == OverflowPolicy.SHRINK
    assert _scene_overflow_policy(OverflowPolicy.CLIP) == OverflowPolicy.CLIP


def test_compile_text_uses_layout_overflow_policy() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="Title",
        message="Message",
    )
    plan = _plan_with_text(slide, text="Long enough body text for a node")
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=default_presentation_design_system(),
    )
    text_nodes = [n for n in scene.nodes if isinstance(n, TextNode)]
    assert text_nodes
    assert text_nodes[0].overflow_policy == OverflowPolicy.WARN


def test_text_node_coerces_legacy_overflow_literals() -> None:
    node = TextNode(
        id="body",
        x=0,
        y=0,
        width=4,
        height=1,
        text="x",
        font_family="Arial",
        font_size=12,
        color="#111",
        line_height=1.2,
        overflow_policy="error",  # type: ignore[arg-type]
    )
    assert node.overflow_policy == OverflowPolicy.WARN
    continued = TextNode(
        id="body2",
        x=0,
        y=0,
        width=4,
        height=1,
        text="x",
        font_family="Arial",
        font_size=12,
        color="#111",
        line_height=1.2,
        overflow_policy="continue",  # type: ignore[arg-type]
    )
    assert continued.overflow_policy == OverflowPolicy.SPLIT


def test_empty_text_element_records_warning() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="Title",
        message="Message",
    )
    plan = _plan_with_text(slide, text="   ", element_id="empty_body")
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=default_presentation_design_system(),
        content_bundle=SlideContentBundle(),
    )
    assert not [n for n in scene.nodes if isinstance(n, TextNode)]
    assert any(w.startswith("EMPTY_TEXT_DROPPED:empty_body") for w in scene.warnings)


def test_scene_qa_aliases_match_slide_layer_codes() -> None:
    assert (
        SceneSemanticCheckCode.BEFORE_AFTER_UNPAIRED
        == "SEMANTIC.BEFORE_AFTER_MISMATCH"
    )
    assert (
        SceneSemanticCheckCode.PROJECT_PHOTO_WITHOUT_SOURCE
        == "SEMANTIC.PROJECT_ASSET_WITHOUT_SOURCE"
    )
