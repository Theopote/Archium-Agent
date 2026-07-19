"""Tests for composite operation support policy."""

from uuid import uuid4

from archium.application.visual.composite_operation_policy import (
    SUPPORTED_COMPOSITE_OPERATIONS,
    assert_composite_operations_supported,
)
from archium.domain.visual.atomic_operation import (
    LockOperation,
    MoveOperation,
    ReduceTextOperation,
    OperationType,
)


def test_all_operation_types_covered_in_policy() -> None:
    expected = {
        OperationType.LOCK,
        OperationType.UNLOCK,
        OperationType.MOVE,
        OperationType.SWAP,
        OperationType.RESIZE,
        OperationType.CHANGE_LAYOUT,
        OperationType.ENLARGE_HERO,
        OperationType.INCREASE_WHITESPACE,
        OperationType.REDUCE_TEXT,
        OperationType.UPDATE_ELEMENT_TEXT,
        OperationType.SET_HERO_ASSET,
        OperationType.REMOVE_ASSET,
        OperationType.SET_ELEMENT_ASSET,
    }
    assert expected == SUPPORTED_COMPOSITE_OPERATIONS


def test_allows_typical_composite_chain() -> None:
    assert_composite_operations_supported(
        [
            LockOperation(uuid4()),
            MoveOperation(uuid4(), "right"),
            ReduceTextOperation(uuid4(), reduce_lines=2),
        ]
    )
