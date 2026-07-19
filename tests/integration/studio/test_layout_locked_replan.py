"""Integration tests for Studio layout candidate and locked-element behavior."""

from __future__ import annotations

import inspect

from archium.application.visual.layout_locked import preserve_locked_elements
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.domain.visual.enums import LayoutElementRole
from archium.domain.visual.layout import LayoutElement
from tests.unit.visual.test_layout_locked import _sample_plan


def test_generate_candidates_accepts_previous_layout_plan_parameter() -> None:
    params = inspect.signature(LayoutPlanningService.generate_candidates).parameters
    assert "previous_layout_plan" in params


def test_preserve_locked_elements_merges_by_element_id() -> None:
    locked = LayoutElement(
        id="title",
        role=LayoutElementRole.TITLE,
        content_type="text",
        text_content="锁定",
        x=0.5,
        y=0.5,
        width=9.0,
        height=0.7,
        locked=True,
    )
    fresh = LayoutElement(
        id="title",
        role=LayoutElementRole.TITLE,
        content_type="text",
        text_content="新标题",
        x=2.0,
        y=2.0,
        width=6.0,
        height=0.5,
        locked=False,
    )
    previous = _sample_plan(elements=[locked])
    generated = _sample_plan(elements=[fresh])
    merged = preserve_locked_elements(generated, previous)
    title = merged.element_by_id("title")
    assert title is not None
    assert title.locked is True
    assert title.x == 0.5
    assert title.text_content == "锁定"


def test_layout_planning_module_imports_preserve_helper() -> None:
    source = inspect.getsource(LayoutPlanningService.generate_candidates)
    assert "preserve_locked_elements" in source
