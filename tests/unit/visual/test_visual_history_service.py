"""Unit tests for visual revision fingerprinting."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.visual_history_service import (
    VisualHistoryService,
    visual_snapshot_fingerprint,
)
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan


def _slide() -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="核心信息。",
    )


def test_visual_snapshot_fingerprint_ignores_version_bump() -> None:
    plan_v1 = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        version=1,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=8,
                height=3,
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    plan_v2 = plan_v1.model_copy(update={"version": 2})
    snapshot_v1 = {
        "kind": "slide_visual_state",
        "visual_intent": None,
        "layout_plan": plan_v1.model_dump(mode="json"),
    }
    snapshot_v2 = {
        "kind": "slide_visual_state",
        "visual_intent": None,
        "layout_plan": plan_v2.model_dump(mode="json"),
    }
    assert visual_snapshot_fingerprint(snapshot_v1) == visual_snapshot_fingerprint(snapshot_v2)


def test_latest_restorable_revision_uses_fingerprint_not_full_dump() -> None:
    slide = _slide()
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        version=1,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=8,
                height=3,
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    service = VisualHistoryService.__new__(VisualHistoryService)
    current = service._build_snapshot(slide=slide, visual_intent=None, layout_plan=plan)
    stored = {
        **current,
        "layout_plan": {
            **plan.model_dump(mode="json"),
            "version": 99,
            "updated_at": "2099-01-01T00:00:00Z",
        },
    }
    assert service._visual_snapshot_matches(stored, current)


def test_latest_restorable_revision_detects_geometry_change() -> None:
    slide = _slide()
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=8,
                height=3,
            )
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    moved = plan.model_copy(
        update={
            "elements": [
                plan.elements[0].model_copy(update={"x": 2.0}),
            ]
        }
    )
    service = VisualHistoryService.__new__(VisualHistoryService)
    current = service._build_snapshot(slide=slide, visual_intent=None, layout_plan=plan)
    stored = service._build_snapshot(slide=slide, visual_intent=None, layout_plan=moved)
    assert not service._visual_snapshot_matches(stored, current)
