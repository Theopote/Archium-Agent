"""Unit tests for RenderScene domain model."""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    RenderScene,
    TextNode,
    compute_scene_hash,
)


def test_render_scene_requires_unique_node_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        RenderScene(
            slide_id=uuid4(),
            layout_plan_id=uuid4(),
            page_width=10,
            page_height=5.625,
            background=BackgroundStyle(color="#FFFFFF"),
            nodes=[
                TextNode(
                    id="title",
                    x=0,
                    y=0,
                    width=8,
                    height=1,
                    text="Title",
                    font_family="Arial",
                    font_size=24,
                    color="#111111",
                    line_height=1.2,
                ),
                TextNode(
                    id="title",
                    x=0,
                    y=1,
                    width=8,
                    height=1,
                    text="Duplicate",
                    font_family="Arial",
                    font_size=16,
                    color="#111111",
                    line_height=1.2,
                ),
            ],
        )


def test_compute_scene_hash_is_stable() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#F7F6F3"),
        nodes=[
            TextNode(
                id="title",
                x=0.7,
                y=0.45,
                width=8,
                height=0.6,
                text="测试标题",
                font_family="Microsoft YaHei",
                font_size=34,
                font_weight=700,
                color="#1A1A1A",
                line_height=1.35,
            )
        ],
    )
    first = compute_scene_hash(scene)
    second = compute_scene_hash(scene)
    assert first == second
    assert len(first) == 64


def test_drawing_node_defaults_to_contain() -> None:
    node = DrawingNode(
        id="hero",
        x=1,
        y=1,
        width=6,
        height=3,
        asset_path="/tmp/plan.png",
        drawing_type="site_plan",
    )
    assert node.fit_mode == "contain"
    assert node.crop_allowed is False
