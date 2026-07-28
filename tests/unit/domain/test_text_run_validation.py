"""Unit tests for TextRun / TextNode.runs domain helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
    TextRun,
    effective_run_style,
    replace_text_node_content,
    set_text_node_runs,
)


def _text_node(**kwargs: object) -> TextNode:
    defaults: dict[str, object] = {
        "id": "title",
        "x": 0.5,
        "y": 0.5,
        "width": 8.0,
        "height": 0.8,
        "text": "标题 Title",
        "font_family": "Arial",
        "font_size": 28.0,
        "font_weight": 400,
        "color": "#111111",
        "line_height": 1.3,
    }
    defaults.update(kwargs)
    return TextNode(**defaults)  # type: ignore[arg-type]


def test_runs_derive_text_on_validate() -> None:
    node = _text_node(
        text="stale",
        runs=[
            TextRun(text="中文", font_weight=700),
            TextRun(text=" Title", font_weight=400, color="#666666"),
        ],
    )
    assert node.text == "中文 Title"


def test_set_text_node_runs_updates_paragraphs() -> None:
    node = _text_node()
    set_text_node_runs(
        node,
        [
            TextRun(text="方案", font_weight=700),
            TextRun(text=" Concept", font_weight=400),
        ],
    )
    assert node.text == "方案 Concept"
    assert len(node.paragraphs) == 1
    assert node.paragraphs[0].text == "方案 Concept"


def test_replace_text_collapses_runs_preserving_first_style() -> None:
    node = _text_node(
        runs=[
            TextRun(text="旧", font_weight=700, color="#AA0000"),
            TextRun(text="文", font_weight=400),
        ]
    )
    replace_text_node_content(node, "新标题")
    assert node.text == "新标题"
    assert len(node.runs) == 1
    assert node.runs[0].font_weight == 700
    assert node.runs[0].color == "#AA0000"


def test_effective_run_style_inherits_node_defaults() -> None:
    node = _text_node(font_size=24.0, color="#222222", font_weight=500)
    run = TextRun(text="EN", font_weight=700)
    style = effective_run_style(node, run)
    assert style["font_weight"] == 700
    assert style["font_size"] == 24.0
    assert style["color"] == "#222222"


def test_set_text_node_runs_rejects_empty() -> None:
    node = _text_node()
    with pytest.raises(ValueError, match="at least one"):
        set_text_node_runs(node, [])


def test_scene_accepts_text_with_runs() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            _text_node(
                runs=[
                    TextRun(text="交通", font_weight=700),
                    TextRun(text=" Organization", font_weight=400),
                ]
            )
        ],
    )
    node = scene.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.text == "交通 Organization"
