"""Unit tests for locked element preservation during layout replan."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_locked import preserve_locked_elements
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    LayoutValidationStatus,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan


def _sample_plan(*, elements: list[LayoutElement]) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10.0,
        page_height=7.5,
        hero_element_id=elements[0].id if elements else None,
        reading_order=[element.id for element in elements],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        validation_status=LayoutValidationStatus.PENDING,
        elements=elements,
    )


def test_preserve_locked_elements_keeps_geometry_and_content() -> None:
    locked_title = LayoutElement(
        id="title",
        role=LayoutElementRole.TITLE,
        content_type=LayoutContentType.TEXT,
        text_content="锁定标题",
        x=1.0,
        y=1.0,
        width=8.0,
        height=0.8,
        locked=True,
    )
    unlocked_body = LayoutElement(
        id="body",
        role=LayoutElementRole.BODY_TEXT,
        content_type=LayoutContentType.TEXT,
        text_content="正文",
        x=1.0,
        y=2.0,
        width=8.0,
        height=4.0,
        locked=False,
    )
    previous = _sample_plan(elements=[locked_title, unlocked_body])

    new_title = locked_title.model_copy(
        update={"x": 2.0, "y": 2.0, "width": 6.0, "height": 0.5, "locked": False}
    )
    new_body = unlocked_body.model_copy(update={"x": 2.0, "y": 3.0, "width": 6.0, "height": 3.0})
    generated = _sample_plan(elements=[new_title, new_body])

    merged = preserve_locked_elements(generated, previous)
    preserved = merged.element_by_id("title")
    body = merged.element_by_id("body")

    assert preserved is not None
    assert preserved.locked is True
    assert preserved.x == 1.0
    assert preserved.text_content == "锁定标题"
    assert body is not None
    assert body.x == 2.0


def test_preserve_locked_elements_without_previous_returns_new_plan() -> None:
    element = LayoutElement(
        id="hero",
        role=LayoutElementRole.HERO_VISUAL,
        content_type=LayoutContentType.IMAGE,
        x=0.5,
        y=1.0,
        width=9.0,
        height=5.0,
    )
    plan = _sample_plan(elements=[element])
    assert preserve_locked_elements(plan, None) == plan
