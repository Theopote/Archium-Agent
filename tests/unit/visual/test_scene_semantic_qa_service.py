"""Unit tests for Scene Semantic QA (WP H)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.scene_qa import SceneSemanticCheckCode


def _scene(*, nodes: list, warnings: list[str] | None = None) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=nodes,
        warnings=list(warnings or []),
    )


def test_drawing_cover_warning_emits_finding() -> None:
    scene = _scene(
        nodes=[
            DrawingNode(
                id="hero",
                x=0.5,
                y=0.5,
                width=6,
                height=4,
                asset_path="a.png",
                drawing_type="site_plan",
            )
        ],
        warnings=["DRAWING_COVER_MODE_FORBIDDEN:hero"],
    )
    report = run_scene_semantic_qa(uuid4(), [scene])
    codes = {finding.check_code for finding in report.findings}
    assert SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN in codes


def test_ai_image_presented_as_project() -> None:
    scene = _scene(
        nodes=[
            ImageNode(
                id="hero",
                semantic_role="project_photo",
                x=1,
                y=1,
                width=4,
                height=3,
                asset_path="ai.png",
                asset_origin="ai_generated",
            )
        ]
    )
    report = run_scene_semantic_qa(uuid4(), [scene])
    assert any(
        finding.check_code == SceneSemanticCheckCode.AI_IMAGE_PRESENTED_AS_REAL_PROJECT
        for finding in report.findings
    )


def test_unresolved_asset_emits_image_not_rendered() -> None:
    scene = _scene(
        nodes=[
            ImageNode(
                id="hero",
                x=1,
                y=1,
                width=4,
                height=3,
                asset_path="",
                asset_unresolved=True,
            )
        ]
    )
    report = run_scene_semantic_qa(uuid4(), [scene])
    assert any(
        finding.check_code == SceneSemanticCheckCode.IMAGE_NOT_RENDERED
        for finding in report.findings
    )


def test_font_too_small() -> None:
    scene = _scene(
        nodes=[
            TextNode(
                id="title",
                x=0.5,
                y=0.5,
                width=8,
                height=0.5,
                text="标题",
                font_family="Test",
                font_size=7,
                color="#000",
                line_height=1.2,
                minimum_font_size=8,
            )
        ]
    )
    report = run_scene_semantic_qa(uuid4(), [scene])
    assert any(
        finding.check_code == SceneSemanticCheckCode.FONT_TOO_SMALL for finding in report.findings
    )


def test_stock_image_as_reference_role_skips() -> None:
    scene = _scene(
        nodes=[
            ImageNode(
                id="ref",
                semantic_role="reference_case_photo",
                x=1,
                y=1,
                width=3,
                height=2,
                asset_path="stock.png",
                asset_origin="stock_image",
            )
        ]
    )
    report = run_scene_semantic_qa(uuid4(), [scene])
    assert not any(
        finding.check_code == SceneSemanticCheckCode.STOCK_IMAGE_PRESENTED_AS_PROJECT
        for finding in report.findings
    )
