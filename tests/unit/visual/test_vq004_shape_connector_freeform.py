"""VQ-004: Shape / Connector / Freeform formal rendering on the main chain."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.graphic_motif import (
    apply_graphic_motif_to_scene,
    compose_graphic_motif,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
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
from archium.domain.visual.render_scene import (
    ConnectorNode,
    FreeformNode,
    ShapeNode,
    TextNode,
)
from archium.domain.visual.visual_concept import FRAGMENT_TO_NETWORK_CONCEPT, PATH_TO_EXPERIENCE_CONCEPT
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.visual_language.graphic_motif import MotifType
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


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


def _plan_with_title(title: str = "流线冲突") -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
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
                y=0.35,
                width=9,
                height=0.7,
                style_token="title",
            )
        ],
        reading_order=["title"],
    )


def test_compile_shape_honors_ellipse_and_stroke_only() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="分析")
    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=design.id,
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="ring",
                role=LayoutElementRole.DECORATION,
                content_type=LayoutContentType.SHAPE,
                x=2,
                y=1.5,
                width=3,
                height=2,
                shape_kind="ellipse",
                fill_color=None,
                stroke_color="#C45C26",
                stroke_width=1.25,
                opacity=0.7,
            )
        ],
        reading_order=["ring"],
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    ring = next(n for n in scene.nodes if isinstance(n, ShapeNode) and n.id == "ring")
    assert ring.shape_kind == "ellipse"
    assert ring.fill_color is None
    assert ring.stroke_width == 1.25
    assert ring.opacity == 0.7


def test_flow_motif_emits_connectors_between_nodes() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="流线冲突")
    plan = _plan_with_title("流线冲突")
    plan = plan.model_copy(update={"slide_id": slide.id})
    intent = VisualIntent(
        slide_id=slide.id,
        communication_goal="conflict",
        audience_takeaway="nodes",
        visual_priority="diagram",
        dominant_content_type=VisualContentType.ANALYTICAL_DIAGRAM,
        continuity_role=ContinuityRole.EVIDENCE,
    )
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
        visual_intent=intent,
    )
    motif = compose_graphic_motif(
        slide=slide,
        layout_plan=plan,
        concept=FRAGMENT_TO_NETWORK_CONCEPT,
    )
    assert motif.motif_type == MotifType.FLOW_NODES
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#C45C26")
    markers = [
        n for n in scene.nodes if isinstance(n, ShapeNode) and n.id.startswith("vl_motif_node_")
    ]
    connectors = [
        n
        for n in scene.nodes
        if isinstance(n, ConnectorNode) and n.id.startswith("vl_motif_connector_")
    ]
    assert len(markers) >= 2
    assert len(connectors) >= 1
    assert connectors[0].arrow_end is True
    assert connectors[0].routing == "elbow"
    assert "vq4_connector_motif" in scene.warnings


def test_path_motif_emits_freeform_polyline() -> None:
    motif = compose_graphic_motif(
        slide=_slide(title="空间序列"),
        concept=PATH_TO_EXPERIENCE_CONCEPT,
    )
    assert motif.motif_type == MotifType.PATH_SEQUENCE
    design = default_presentation_design_system()
    slide = _slide(title="空间序列")
    plan = _plan_with_title("空间序列")
    plan = plan.model_copy(update={"slide_id": slide.id})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#4A7C59")
    freeforms = [
        n
        for n in scene.nodes
        if isinstance(n, FreeformNode) and n.id.startswith("vl_motif_")
    ]
    assert freeforms
    assert freeforms[0].closed is False
    assert len(freeforms[0].points) >= 3
    assert "vq4_freeform_motif" in scene.warnings


def test_pptx_adapter_exports_connector_and_freeform_instructions() -> None:
    design = default_presentation_design_system()
    slide = _slide(title="流线冲突")
    plan = _plan_with_title()
    plan = plan.model_copy(update={"slide_id": slide.id})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    motif = compose_graphic_motif(slide=slide, concept=FRAGMENT_TO_NETWORK_CONCEPT)
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#C45C26")
    instruction = RenderScenePptxAdapter().render_slide(scene)
    payload = instruction.to_dict() if hasattr(instruction, "to_dict") else instruction
    elements = payload.get("elements") if isinstance(payload, dict) else instruction.elements
    types = {el.get("content_type") for el in elements}
    assert "connector" in types
    connector = next(el for el in elements if el.get("content_type") == "connector")
    assert len(connector.get("points") or []) >= 2
    assert connector.get("arrow_end") is True
    assert connector.get("stroke_dash") in {"solid", "dash", "dot"}
    indexes = [
        n
        for n in scene.nodes
        if isinstance(n, TextNode) and n.semantic_role == "graphic_motif_index"
    ]
    assert indexes


def test_module_index_emits_cross_freeform_markers() -> None:
    from archium.domain.visual.visual_concept import CORE_TO_EXPANSION_CONCEPT

    motif = compose_graphic_motif(
        slide=_slide(title="指标"),
        concept=CORE_TO_EXPANSION_CONCEPT,
    )
    assert motif.motif_type == MotifType.MODULE_INDEX
    design = default_presentation_design_system()
    slide = _slide(title="指标")
    plan = _plan_with_title("关键指标")
    plan = plan.model_copy(update={"slide_id": slide.id})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#C45C26")
    crosses = [
        n
        for n in scene.nodes
        if isinstance(n, FreeformNode) and n.id.startswith("vl_motif_node_")
    ]
    assert crosses
    assert crosses[0].closed is False
    assert len(crosses[0].points) >= 3


def test_before_after_emits_diagonal_cut_freeform() -> None:
    from archium.domain.visual.visual_concept import EXISTING_TO_TRANSFORMATION_CONCEPT

    motif = compose_graphic_motif(
        slide=_slide(title="更新对比"),
        concept=EXISTING_TO_TRANSFORMATION_CONCEPT,
    )
    assert motif.motif_type == MotifType.BEFORE_AFTER_SLICE
    design = default_presentation_design_system()
    slide = _slide(title="更新对比")
    plan = _plan_with_title("更新对比")
    plan = plan.model_copy(update={"slide_id": slide.id})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#C45C26")
    cut = next(
        (
            n
            for n in scene.nodes
            if isinstance(n, FreeformNode) and n.id == "vl_motif_slice_cut"
        ),
        None,
    )
    assert cut is not None
    assert cut.closed is False
    assert cut.stroke_dash == "dash"
    instruction = RenderScenePptxAdapter().render_slide(scene)
    payload = instruction.to_dict()
    free = next(el for el in payload["elements"] if el.get("id") == "vl_motif_slice_cut")
    assert free["stroke_dash"] == "dash"
    assert free["content_type"] == "freeform"


def test_png_and_html_render_connectors(tmp_path) -> None:
    from pathlib import Path

    from archium.infrastructure.renderers.html_renderer import HtmlRenderer
    from archium.infrastructure.renderers.png_renderer import PngRenderer

    design = default_presentation_design_system()
    slide = _slide(title="流线冲突")
    plan = _plan_with_title()
    plan = plan.model_copy(update={"slide_id": slide.id})
    scene = RenderSceneCompiler().compile(
        slide=slide,
        layout_plan=plan,
        design_system=design,
    )
    motif = compose_graphic_motif(slide=slide, concept=FRAGMENT_TO_NETWORK_CONCEPT)
    scene = apply_graphic_motif_to_scene(scene, motif, accent_hex="#C45C26")
    out = Path(tmp_path) / "vq4.png"
    PngRenderer().render(scene, out)
    assert out.is_file() and out.stat().st_size > 800
    html = HtmlRenderer().render(scene)
    assert "vl_motif_connector_" in html or "marker-end" in html
