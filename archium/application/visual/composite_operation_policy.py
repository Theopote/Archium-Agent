"""Policy for which composite visual operations are safe to execute."""

from __future__ import annotations

from archium.domain.visual.atomic_operation import AtomicOperation, OperationType
from archium.exceptions import WorkflowError

SUPPORTED_COMPOSITE_OPERATIONS: frozenset[OperationType] = frozenset(
    {
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
)


def assert_composite_operations_supported(operations: list[AtomicOperation]) -> None:
    """Reject composite transactions that include unimplemented operation types."""
    unsupported = [
        operation
        for operation in operations
        if operation.operation_type not in SUPPORTED_COMPOSITE_OPERATIONS
    ]
    if not unsupported:
        return

    first = unsupported[0]
    raise WorkflowError(f"复合操作「{first.operation_type.value}」暂未支持。")
