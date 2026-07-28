"""Silhouette mask → Freeform overlay migration tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    FreeformNode,
    ImageNode,
    Point,
    RenderScene,
    refresh_freeform_geometry,
)
from archium.domain.visual.studio_command import ApplySilhouetteMaskCommand
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


def test_apply_silhouette_sets_mask_and_freeform_overlay() -> None:
    scene = _scene(
        ImageNode(
            id="hero",
            x=1,
            y=1,
            width=4,
            height=3,
            storage_uri="project://hero.png",
        )
    )
    result = StudioCommandExecutor().execute(
        scene,
        ApplySilhouetteMaskCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="hero",
            preset="diamond",
            freeform_id="hero__silhouette",
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    image = result.candidate_scene.node_by_id("hero")
    assert isinstance(image, ImageNode)
    assert image.image_mask == "silhouette"
    frame = result.candidate_scene.node_by_id("hero__silhouette")
    assert isinstance(frame, FreeformNode)
    assert len(frame.points) == 4
    assert frame.fill_color is None


def test_adapter_emits_image_silhouette_and_freeform() -> None:
    image = ImageNode(
        id="hero",
        x=1,
        y=1,
        width=4,
        height=3,
        storage_uri="project://hero.png",
        image_mask="silhouette",
    )
    frame = FreeformNode(
        id="hero__silhouette",
        x=1.2,
        y=1.2,
        width=3.6,
        height=2.6,
        points=[
            Point(x=3.0, y=1.2),
            Point(x=4.8, y=2.5),
            Point(x=3.0, y=3.8),
            Point(x=1.2, y=2.5),
        ],
        stroke_color="#FFFFFF",
    )
    refresh_freeform_geometry(frame)
    scene = _scene(image, frame)
    instruction = RenderScenePptxAdapter().render_slide(scene)
    by_id = {item["id"]: item for item in instruction.elements}
    assert by_id["hero"]["image_mask"] == "silhouette"
    assert by_id["hero__silhouette"]["content_type"] == "freeform"
    assert len(by_id["hero__silhouette"]["points"]) == 4
