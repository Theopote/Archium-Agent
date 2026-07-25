"""Unit tests for Visual Thinking slots bound to DesignIntent."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision.visual_thinking_slots import (
    VISUAL_THINKING_SLOTS,
    focus_hint_for_slot,
    intent_binding_lines,
    slot_by_key,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.spatial_design import SpatialIntent


def test_four_visual_thinking_slots() -> None:
    assert [slot.key for slot in VISUAL_THINKING_SLOTS] == [
        "atmosphere",
        "space",
        "material",
        "massing",
    ]
    assert slot_by_key("material") is not None
    assert slot_by_key("unknown") is None


def test_intent_binding_lines_for_space_slot() -> None:
    direction = ConceptDirection(
        id=uuid4(),
        project_id=uuid4(),
        title="自然共生",
        theme="建筑融入山体",
        spatial_strategy="低体量连续屋顶",
        spatial_intent=SpatialIntent(
            spatial_relationships="建筑嵌入坡地",
            movement_experience="沿等高线漫游",
        ),
    )
    slot = slot_by_key("space")
    assert slot is not None
    lines = intent_binding_lines(direction, slot)
    assert any("建筑融入山体" in line for line in lines)
    assert any("低体量" in line for line in lines)
    hint = focus_hint_for_slot(direction, slot)
    assert "低体量" in hint or "融入山体" in hint
