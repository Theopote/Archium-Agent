"""Unit tests for layered proposal scene QA."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_deterministic_qa_service import run_proposal_scene_qa
from archium.domain.visual.page_quality import IssueSeverity
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.validation import (
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_UNRESOLVED_ASSET_PATH,
)


def _text_node(
    *,
    node_id: str,
    x: float = 0.5,
    y: float = 1.0,
    width: float = 2.0,
    height: float = 0.4,
    text: str = "text",
) -> TextNode:
    return TextNode(
        id=node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        z_index=1,
        text=text,
        font_family="Arial",
        font_size=12,
        color="#000000",
        line_height=1.2,
    )


def _scene(*nodes) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def test_geometry_qa_detects_overlap_and_out_of_bounds() -> None:
    scene = _scene(
        _text_node(node_id="a", x=1.0, y=1.0, width=2.0, height=1.0),
        _text_node(node_id="b", x=1.5, y=1.2, width=2.0, height=1.0),
        _text_node(node_id="outside", x=9.5, y=0.2, width=2.0, height=0.5),
    )
    result = run_proposal_scene_qa(uuid4(), scene, include_post_render=False)
    codes = {issue.code for issue in result.issues}
    assert LAYOUT_ELEMENT_OVERLAP in codes
    assert LAYOUT_ELEMENT_OUTSIDE_PAGE in codes
    assert result.layers["geometry"]


def test_asset_qa_detects_unresolved_image() -> None:
    scene = _scene(
        ImageNode(
            id="photo",
            x=1,
            y=1,
            width=3,
            height=2,
            z_index=1,
            asset_unresolved=True,
        )
    )
    result = run_proposal_scene_qa(uuid4(), scene, include_post_render=False)
    assert any(issue.code == LAYOUT_UNRESOLVED_ASSET_PATH for issue in result.layers["asset"])


def test_drawing_qa_detects_invalid_fit_mode() -> None:
    node = DrawingNode.model_construct(
        id="plan",
        x=1,
        y=1,
        width=4,
        height=3,
        z_index=1,
        storage_uri="project://plan.png",
        asset_path="project://plan.png",
        fit_mode="cover",
    )
    scene = _scene(node)
    result = run_proposal_scene_qa(uuid4(), scene, include_post_render=False)
    drawing_codes = {issue.code for issue in result.layers["drawing"]}
    assert any("DRAWING" in code or "COVER" in code for code in drawing_codes)


def test_proposal_qa_merges_layers_without_duplicates() -> None:
    scene = _scene(_text_node(node_id="title", text="短标题"))
    result = run_proposal_scene_qa(uuid4(), scene, include_post_render=False)
    assert "semantic" in result.layers
    assert "geometry" in result.layers
    assert "asset" in result.layers
    assert "drawing" in result.layers
    assert result.preview_render_success is True
    keys = {(issue.code, tuple(sorted(issue.evidence))) for issue in result.issues}
    assert len(keys) == len(result.issues)


def test_blocker_issues_use_blocker_severity_for_geometry() -> None:
    scene = _scene(_text_node(node_id="outside", x=11.0, y=0.2, width=1.0, height=0.5))
    result = run_proposal_scene_qa(uuid4(), scene, include_post_render=False)
    overlap_issues = [issue for issue in result.layers["geometry"] if issue.code == LAYOUT_ELEMENT_OUTSIDE_PAGE]
    assert overlap_issues
    assert overlap_issues[0].severity == IssueSeverity.BLOCKER
