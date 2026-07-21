"""Unit tests for drawing readability service."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.drawing_readability_service import (
    increase_drawing_readability,
    node_area_ratio,
)
from archium.domain.visual.render_scene import BackgroundStyle, DrawingNode, RenderScene
from archium.domain.visual.studio_command import IncreaseDrawingReadabilityCommand


def test_increase_drawing_readability_meets_target_ratio() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="plan",
                x=2,
                y=1,
                width=3,
                height=2,
                z_index=1,
                storage_uri="project://plan.png",
                asset_path="project://plan.png",
                fit_mode="contain",
            )
        ],
    )
    command = IncreaseDrawingReadabilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="plan",
        target_min_area_ratio=0.45,
    )
    result = increase_drawing_readability(scene, command)
    assert result.area_ratio_after >= 0.45
    assert result.scene.node_by_id("plan").fit_mode == "contain"


def test_noop_when_target_already_met() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="plan",
                x=0.4,
                y=0.4,
                width=9.2,
                height=4.8,
                z_index=1,
                storage_uri="project://plan.png",
                asset_path="project://plan.png",
            )
        ],
    )
    drawing = scene.node_by_id("plan")
    assert drawing is not None
    assert node_area_ratio(drawing, scene) >= 0.45
    result = increase_drawing_readability(
        scene,
        IncreaseDrawingReadabilityCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="plan",
            target_min_area_ratio=0.45,
        ),
    )
    assert result.actions == ()
