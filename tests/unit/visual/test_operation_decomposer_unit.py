"""Unit tests for OperationDecomposer."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.operation_decomposer import OperationDecomposer
from archium.domain.visual.atomic_operation import LockOperation, SwapOperation
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.nlp_parser import Modifier, ModifierType, ParsedIntent
from archium.domain.visual.slide_edit_snapshot import SlideEditSnapshot
from archium.exceptions import WorkflowError


def _caption_layout() -> tuple[LayoutPlan, str]:
    caption_id = str(uuid4())
    layout_plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id=caption_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=100,
                y=450,
                width=400,
                height=100,
                locked=False,
            ),
        ],
    )
    return layout_plan, caption_id


def test_decompose_preserve_and_move() -> None:
    drawing_id = str(uuid4())
    caption_id = str(uuid4())
    layout_plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id=drawing_id,
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=100,
                y=100,
                width=400,
                height=300,
                locked=False,
            ),
            LayoutElement(
                id=caption_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=100,
                y=450,
                width=400,
                height=100,
                locked=False,
            ),
        ],
    )
    snapshot = SlideEditSnapshot(
        slide_id=layout_plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=layout_plan,
    )
    parsed = ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={"target": "说明", "position": "右边"},
        modifiers=[
            Modifier(
                type=ModifierType.CONSTRAINT,
                target="图纸",
                value="preserve",
                description="keep drawing fixed",
            ),
        ],
        confidence=0.85,
    )

    operations = OperationDecomposer().decompose(parsed, snapshot)

    assert isinstance(operations[0], LockOperation)
    assert operations[0].target_element_id == drawing_id
    assert any(type(op).__name__ == "MoveOperation" for op in operations[1:])


def test_decompose_move_and_reduce_text() -> None:
    layout_plan, caption_id = _caption_layout()
    snapshot = SlideEditSnapshot(
        slide_id=layout_plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=layout_plan,
    )
    parsed = ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={
            "target": "说明",
            "position": "右边",
            "multi_step_operations": [
                {"operation": "move_to", "targets": ["说明", "右边"]},
            ],
            "reduce_lines": 2,
            "reduce_text_element": "说明",
        },
        modifiers=[],
        confidence=0.75,
    )

    operations = OperationDecomposer().decompose(parsed, snapshot)
    op_types = [type(op).__name__ for op in operations]
    assert "MoveOperation" in op_types
    assert "ReduceTextOperation" in op_types
    assert caption_id in {op.target_element_id for op in operations if op.target_element_id}


def test_decompose_swap_operation() -> None:
    left_id = str(uuid4())
    right_id = str(uuid4())
    layout_plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id=left_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=80,
                y=200,
                width=120,
                height=60,
                text_content="left",
            ),
            LayoutElement(
                id=right_id,
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                x=480,
                y=260,
                width=120,
                height=60,
                text_content="right",
            ),
        ],
    )
    parsed = ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={
            "multi_step_operations": [
                {"operation": "swap", "targets": [left_id, right_id]},
            ],
        },
        modifiers=[],
        confidence=0.9,
    )
    operations = OperationDecomposer().decompose(
        parsed,
        SlideEditSnapshot(
            slide_id=layout_plan.slide_id,
            presentation_id=uuid4(),
            visual_intent=None,
            layout_plan=layout_plan,
        ),
    )
    assert len(operations) == 1
    assert isinstance(operations[0], SwapOperation)


def test_decompose_raises_when_no_operations() -> None:
    layout_plan, _ = _caption_layout()
    parsed = ParsedIntent(
        intent=VisualEditIntent.RESTORE_PREVIOUS,
        params={},
        modifiers=[],
        confidence=0.5,
    )
    with pytest.raises(WorkflowError, match="no valid operations"):
        OperationDecomposer().decompose(
            parsed,
            SlideEditSnapshot(
                slide_id=layout_plan.slide_id,
                presentation_id=uuid4(),
                visual_intent=None,
                layout_plan=layout_plan,
            ),
        )


def test_decompose_enlarge_hero_and_increase_whitespace() -> None:
    layout_plan, _ = _caption_layout()
    snapshot = SlideEditSnapshot(
        slide_id=layout_plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=layout_plan,
    )
    hero_ops = OperationDecomposer().decompose(
        ParsedIntent(
            intent=VisualEditIntent.ENLARGE_HERO,
            params={"adjustment_strength": 0.5},
            modifiers=[],
            confidence=0.9,
        ),
        snapshot,
    )
    assert len(hero_ops) == 1
    assert hero_ops[0].operation_type.value == "enlarge_hero"

    whitespace_ops = OperationDecomposer().decompose(
        ParsedIntent(
            intent=VisualEditIntent.INCREASE_WHITESPACE,
            params={},
            modifiers=[],
            confidence=0.9,
        ),
        snapshot,
    )
    assert len(whitespace_ops) == 1
    assert whitespace_ops[0].operation_type.value == "increase_whitespace"


def test_decompose_lock_and_unlock_by_element_id() -> None:
    layout_plan, caption_id = _caption_layout()
    snapshot = SlideEditSnapshot(
        slide_id=layout_plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=layout_plan,
    )
    lock_ops = OperationDecomposer().decompose(
        ParsedIntent(
            intent=VisualEditIntent.LOCK_ELEMENT,
            params={"element_id": caption_id},
            modifiers=[],
            confidence=0.9,
        ),
        snapshot,
    )
    assert lock_ops[0].target_element_id == caption_id

    unlock_ops = OperationDecomposer().decompose(
        ParsedIntent(
            intent=VisualEditIntent.UNLOCK_ELEMENT,
            params={"element_id": caption_id},
            modifiers=[],
            confidence=0.9,
        ),
        snapshot,
    )
    assert unlock_ops[0].target_element_id == caption_id


def test_decompose_change_layout_with_layout_family() -> None:
    layout_plan, _ = _caption_layout()
    snapshot = SlideEditSnapshot(
        slide_id=layout_plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=layout_plan,
    )
    operations = OperationDecomposer().decompose(
        ParsedIntent(
            intent=VisualEditIntent.CHANGE_LAYOUT,
            params={"layout_family": LayoutFamily.HERO},
            modifiers=[],
            confidence=0.9,
        ),
        snapshot,
    )
    assert len(operations) == 1
    assert operations[0].operation_type.value == "change_layout"



