"""Unit tests for canvas pointer-up → Studio command bridge."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.ui.components.canvas_editor import convert_elements_for_canvas
from archium.ui.studio.canvas_command_bridge import (
    bump_canvas_generation,
    canvas_component_key,
    geometry_event_fingerprint,
)


def test_geometry_event_fingerprint_is_stable() -> None:
    first = geometry_event_fingerprint("move", "hero", 12.5, 30.0)
    second = geometry_event_fingerprint("move", "hero", 12.50001, 30.00001)
    assert first == second


def test_canvas_component_key_bumps_after_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    slide_id = uuid4()
    state: dict[str, object] = {}

    class _SessionState(dict):
        def get(self, key, default=None):  # type: ignore[no-untyped-def]
            return super().get(key, default)

    import streamlit as st

    monkeypatch.setattr(st, "session_state", _SessionState(state))
    first = canvas_component_key(slide_id)
    bump_canvas_generation(slide_id)
    second = canvas_component_key(slide_id)
    assert first != second


def test_convert_elements_for_canvas_prefers_render_scene_geometry() -> None:
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10.0,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    scene = RenderScene(
        slide_id=slide_id,
        layout_plan_id=plan.id,
        page_width=10.0,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title_node",
                source_layout_element_id="title",
                x=3.0,
                y=2.0,
                width=4.0,
                height=1.0,
                z_index=1,
                text="标题",
                font_family="Arial",
                font_size=18,
                color="#000000",
                line_height=1.2,
            ),
        ],
    )
    converted = convert_elements_for_canvas(plan, render_scene=scene)
    assert len(converted) == 1
    assert converted[0]["x"] == pytest.approx(30.0)
    assert converted[0]["y"] == pytest.approx((2.0 / 5.625) * 100)
    assert converted[0]["width"] == pytest.approx(40.0)
