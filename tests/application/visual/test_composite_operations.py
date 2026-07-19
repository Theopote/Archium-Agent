"""Tests for composite operation execution with transaction support."""

from uuid import uuid4

import pytest

from archium.domain.visual.atomic_operation import (
    LockOperation,
    MoveOperation,
    ReduceTextOperation,
    SwapOperation,
)
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily, LayoutElementRole, LayoutContentType
from archium.domain.visual.nlp_parser import Modifier, ModifierType, ParsedIntent


class TestOperationDecomposition:
    """Test that composite commands are correctly decomposed."""

    def test_decompose_preserve_and_move(self):
        """Test: '保持图纸不动，把说明放右边'"""
        # Arrange
        from archium.application.visual.operation_decomposer import OperationDecomposer
        from archium.domain.visual.slide import SlideSnapshot
        from archium.domain.visual.layout import LayoutPlan, LayoutElement

        # Create mock slide snapshot
        drawing_id = uuid4()
        caption_id = uuid4()

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
                    id=str(drawing_id),
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.DRAWING,
                    x=100, y=100, width=400, height=300,
                    locked=False,
                ),
                LayoutElement(
                    id=str(caption_id),
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    x=100, y=450, width=400, height=100,
                    locked=False,
                ),
            ],
        )

        slide_snapshot = SlideSnapshot(
            slide_id=uuid4(),
            presentation_id=uuid4(),
            visual_intent=None,
            layout_plan=layout_plan,
        )

        parsed_intent = ParsedIntent(
            intent=VisualEditIntent.CHANGE_LAYOUT,
            params={"target": "说明", "position": "右边"},
            modifiers=[
                Modifier(
                    type=ModifierType.CONSTRAINT,
                    target="图纸",
                    value="preserve",
                    description="约束: 保持图纸不动",
                ),
            ],
            confidence=0.85,
        )

        decomposer = OperationDecomposer()

        # Act
        operations = decomposer.decompose(parsed_intent, slide_snapshot)

        # Assert
        assert len(operations) >= 2, "应该至少有2个操作: 锁定+主操作"

        # First operation should be lock
        assert isinstance(operations[0], LockOperation)
        assert operations[0].target_element_id == drawing_id

        # Subsequent operations should include moving the caption
        op_types = {type(op).__name__ for op in operations[1:]}
        assert "MoveOperation" in op_types


    def test_decompose_move_and_reduce_text(self):
        """Test: '把说明放右边并减少两行文字'"""
        from archium.application.visual.operation_decomposer import OperationDecomposer
        from archium.domain.visual.slide import SlideSnapshot
        from archium.domain.visual.layout import LayoutPlan, LayoutElement

        caption_id = uuid4()

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
                    id=str(caption_id),
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    x=100, y=450, width=400, height=100,
                    locked=False,
                ),
            ],
        )

        slide_snapshot = SlideSnapshot(
            slide_id=uuid4(),
            presentation_id=uuid4(),
            visual_intent=None,
            layout_plan=layout_plan,
        )

        parsed_intent = ParsedIntent(
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
            modifiers=[
                Modifier(
                    type=ModifierType.MULTI_STEP,
                    value={"operation": "move_to", "targets": ["说明", "右边"]},
                    description="位置操作: move_to",
                ),
            ],
            confidence=0.75,
        )

        decomposer = OperationDecomposer()

        # Act
        operations = decomposer.decompose(parsed_intent, slide_snapshot)

        # Assert
        assert len(operations) >= 2, "应该至少有2个操作: 移动+减少文字"

        # Check that we have both move and reduce text operations
        op_types = [type(op).__name__ for op in operations]
        assert "MoveOperation" in op_types or any("move" in str(op.operation_type).lower() for op in operations)
        assert "ReduceTextOperation" in op_types or any("reduce" in str(op.operation_type).lower() for op in operations)


    def test_decompose_full_composite(self):
        """Test: '保持图纸不动，把说明放右边并减少两行文字'"""
        from archium.application.visual.operation_decomposer import OperationDecomposer
        from archium.domain.visual.slide import SlideSnapshot
        from archium.domain.visual.layout import LayoutPlan, LayoutElement

        drawing_id = uuid4()
        caption_id = uuid4()

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
                    id=str(drawing_id),
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.DRAWING,
                    x=100, y=100, width=400, height=300,
                    locked=False,
                ),
                LayoutElement(
                    id=str(caption_id),
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    x=100, y=450, width=400, height=100,
                    locked=False,
                ),
            ],
        )

        slide_snapshot = SlideSnapshot(
            slide_id=uuid4(),
            presentation_id=uuid4(),
            visual_intent=None,
            layout_plan=layout_plan,
        )

        parsed_intent = ParsedIntent(
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
            modifiers=[
                Modifier(
                    type=ModifierType.CONSTRAINT,
                    target="图纸",
                    value="preserve",
                    description="约束: 保持图纸不动",
                ),
                Modifier(
                    type=ModifierType.MULTI_STEP,
                    value={"operation": "move_to", "targets": ["说明", "右边"]},
                    description="位置操作: move_to",
                ),
            ],
            confidence=0.75,
        )

        decomposer = OperationDecomposer()

        # Act
        operations = decomposer.decompose(parsed_intent, slide_snapshot)

        # Assert
        assert len(operations) >= 3, "应该至少有3个操作: 锁定+移动+减少文字"

        # Check execution order: locks first
        assert isinstance(operations[0], LockOperation)
        assert operations[0].target_element_id == drawing_id

        # Remaining operations handle move and text reduction
        remaining_op_types = [type(op).__name__ for op in operations[1:]]
        has_move = any("Move" in t or "move" in str(operations[i].operation_type).lower()
                      for i, t in enumerate(remaining_op_types, 1))
        has_reduce = any("Reduce" in t or "reduce" in str(operations[i].operation_type).lower()
                        for i, t in enumerate(remaining_op_types, 1))

        assert has_move, "应该包含移动操作"
        assert has_reduce, "应该包含减少文字操作"


def test_decompose_swap_produces_two_absolute_moves() -> None:
    """Swap should decompose into two absolute move operations."""
    from archium.application.visual.operation_decomposer import OperationDecomposer
    from archium.domain.visual.slide import SlideSnapshot
    from archium.domain.visual.layout import LayoutPlan, LayoutElement

    left_id = uuid4()
    right_id = uuid4()
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
                id=str(left_id),
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=80,
                y=200,
                width=120,
                height=60,
                text_content="左",
            ),
            LayoutElement(
                id=str(right_id),
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                x=480,
                y=260,
                width=120,
                height=60,
                text_content="右",
            ),
        ],
    )
    parsed = ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={
            "multi_step_operations": [
                {"operation": "swap", "targets": [str(left_id), str(right_id)]},
            ],
        },
        modifiers=[],
        confidence=0.9,
    )
    operations = OperationDecomposer().decompose(
        parsed,
        SlideSnapshot(
            slide_id=layout_plan.slide_id,
            presentation_id=uuid4(),
            visual_intent=None,
            layout_plan=layout_plan,
        ),
    )
    assert len(operations) == 1
    assert isinstance(operations[0], SwapOperation)
    assert operations[0].params["second_element_id"] == str(right_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
