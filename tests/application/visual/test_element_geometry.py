"""Tests for element geometry helpers."""

from uuid import uuid4

from archium.application.visual.element_geometry import (
    compute_element_placement,
    normalize_position,
    reduce_text_content,
)
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan


def test_normalize_position_accepts_chinese() -> None:
    assert normalize_position("右边") == "right"


def test_reduce_text_content_drops_lines() -> None:
    result = reduce_text_content("第一行\n第二行\n第三行", reduce_lines=1)
    assert "第三行" not in result
    assert "第一行" in result


def test_compute_element_placement_moves_to_right_column() -> None:
    plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[],
    )
    element = LayoutElement(
        id="caption",
        role=LayoutElementRole.CAPTION,
        content_type=LayoutContentType.TEXT,
        x=20,
        y=400,
        width=200,
        height=80,
        text_content="说明",
    )
    x, y, width, height = compute_element_placement(element, plan, "right")
    assert x > element.x
    assert width == element.width
    assert height == element.height
    assert y == element.y


def test_absolute_placement() -> None:
    from archium.application.visual.element_geometry import compute_element_placement

    plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[],
    )
    element = LayoutElement(
        id="box",
        role=LayoutElementRole.CAPTION,
        content_type=LayoutContentType.TEXT,
        x=10,
        y=10,
        width=100,
        height=50,
        text_content="test",
    )
    x, y, width, height = compute_element_placement(
        element,
        plan,
        "absolute",
        absolute_x=300,
        absolute_y=200,
    )
    assert x == 300
    assert y == 200
    assert width == 100
