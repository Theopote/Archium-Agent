"""Unit tests for GradientFill domain and PPTX adapter wiring."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.powerpoint_capability import (
    PowerPointDepthStatus,
    PowerPointFidelity,
    assess_scene_node,
    depth_entry,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    GradientFill,
    GradientStop,
    ImageNode,
    RenderScene,
    ShapeNode,
    bottom_fade_gradient,
    gradient_fill_to_payload,
)
from archium.domain.visual.studio_command import SetGradientFillCommand
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def _ctx(scene: RenderScene) -> StudioExecutionContext:
    return StudioExecutionContext(presentation_id=uuid4(), validate_asset_bindings=False)


def test_gradient_fill_round_trip_payload() -> None:
    fill = GradientFill(
        kind="linear",
        angle_deg=90,
        stops=[
            GradientStop(position=0.0, color="#111111", transparency=1.0),
            GradientStop(position=1.0, color="#111111", transparency=0.2),
        ],
    )
    payload = gradient_fill_to_payload(fill)
    restored = GradientFill.model_validate(
        {
            "kind": payload["kind"],
            "angle_deg": payload["angle_deg"],
            "stops": [
                {
                    "position": stop["position"],
                    "color": f"#{stop['color']}",
                    "transparency": stop["transparency"],
                }
                for stop in payload["stops"]  # type: ignore[index]
            ],
        }
    )
    assert restored.angle_deg == 90
    assert len(restored.stops) == 2


def test_bottom_fade_helper() -> None:
    fill = bottom_fade_gradient()
    assert fill.kind == "linear"
    assert fill.angle_deg == 90
    assert fill.stops[0].transparency == 1.0
    assert fill.stops[-1].transparency < 1.0


def test_gradient_depth_is_partial() -> None:
    assert depth_entry("gradient_fill").status is PowerPointDepthStatus.PARTIAL


def test_shape_with_gradient_is_approximate() -> None:
    node = ShapeNode(
        id="panel",
        x=0.5,
        y=0.5,
        width=4,
        height=2,
        fill=GradientFill(
            stops=[
                GradientStop(position=0, color="#000000"),
                GradientStop(position=1, color="#FFFFFF"),
            ]
        ),
    )
    assessment = assess_scene_node(node)
    assert assessment.mapping.fidelity is PowerPointFidelity.APPROXIMATE
    assert "gradient_stops:2" in assessment.detected_features


def test_adapter_emits_fill_for_shape_and_image_fade() -> None:
    shape = ShapeNode(
        id="panel",
        x=0.5,
        y=0.5,
        width=3,
        height=1.5,
        fill_color="#ABCDEF",
        fill=GradientFill(
            angle_deg=0,
            stops=[
                GradientStop(position=0, color="#ABCDEF"),
                GradientStop(position=1, color="#123456"),
            ],
        ),
    )
    image = ImageNode(
        id="hero",
        x=4,
        y=0.5,
        width=5,
        height=3,
        storage_uri="project://hero.png",
        image_mask="gradient_fade",
    )
    scene = _scene(shape, image)
    instruction = RenderScenePptxAdapter().render_slide(scene)
    by_id = {item["id"]: item for item in instruction.elements}
    assert "fill" in by_id["panel"]
    assert by_id["panel"]["fill"]["angle_deg"] == 0
    assert "fill" in by_id["hero"]
    assert len(by_id["hero"]["fill"]["stops"]) >= 2


def test_set_gradient_fill_command_bottom_fade() -> None:
    scene = _scene(
        ImageNode(
            id="hero",
            x=1,
            y=1,
            width=4,
            height=2.5,
            storage_uri="project://a.png",
        )
    )
    result = StudioCommandExecutor().execute(
        scene,
        SetGradientFillCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="hero",
            bottom_fade=True,
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("hero")
    assert isinstance(node, ImageNode)
    assert node.fill is not None
    assert node.image_mask == "gradient_fade"
