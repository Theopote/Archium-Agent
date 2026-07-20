"""Unit tests for canvas editor element conversion and event parsing."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.ui.components.canvas_editor import _convert_elements, parse_canvas_editor_event


def test_convert_elements_marks_drawing_as_locked() -> None:
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=10.0,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="drawing",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.5,
                y=0.5,
                width=6.0,
                height=4.0,
                locked=False,
            ),
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=7.0,
                y=0.5,
                width=2.5,
                height=0.6,
                locked=False,
            ),
        ],
        whitespace_ratio=0.3,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    converted = _convert_elements(plan)
    by_id = {item["id"]: item for item in converted}
    assert by_id["drawing"]["locked"] is True
    assert by_id["drawing"]["content_type"] == "drawing"
    assert by_id["title"]["locked"] is False


def test_parse_edit_text_event() -> None:
    event = parse_canvas_editor_event({"type": "editText", "elementId": "title"})
    assert event == {"type": "editText", "elementId": "title"}
