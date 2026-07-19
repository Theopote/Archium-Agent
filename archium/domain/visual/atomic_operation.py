"""Atomic operations for visual editing transactions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily


class OperationType(StrEnum):
    """Types of atomic operations that can be executed."""

    LOCK = "lock"
    UNLOCK = "unlock"
    MOVE = "move"
    RESIZE = "resize"
    CHANGE_LAYOUT = "change_layout"
    REDUCE_TEXT = "reduce_text"
    ENLARGE_HERO = "enlarge_hero"
    INCREASE_WHITESPACE = "increase_whitespace"
    SET_HERO_ASSET = "set_hero_asset"
    REMOVE_ASSET = "remove_asset"
    UPDATE_ELEMENT_TEXT = "update_element_text"
    SET_ELEMENT_ASSET = "set_element_asset"


@dataclass(frozen=True)
class AtomicOperation:
    """
    An atomic, reversible operation on a slide.

    Each operation represents a single change that can be:
    - Executed independently
    - Validated against constraints
    - Rolled back if the transaction fails
    """

    operation_type: OperationType
    target_element_id: UUID | None
    params: dict[str, Any]

    @property
    def is_lock_operation(self) -> bool:
        """Check if this is a lock/unlock operation."""
        return self.operation_type in {OperationType.LOCK, OperationType.UNLOCK}

    @property
    def modifies_layout(self) -> bool:
        """Check if this operation modifies the layout plan."""
        return self.operation_type in {
            OperationType.CHANGE_LAYOUT,
            OperationType.ENLARGE_HERO,
            OperationType.INCREASE_WHITESPACE,
        }

    @property
    def modifies_content(self) -> bool:
        """Check if this operation modifies content."""
        return self.operation_type in {
            OperationType.REDUCE_TEXT,
            OperationType.UPDATE_ELEMENT_TEXT,
        }

    @property
    def modifies_assets(self) -> bool:
        """Check if this operation modifies assets."""
        return self.operation_type in {
            OperationType.SET_HERO_ASSET,
            OperationType.REMOVE_ASSET,
            OperationType.SET_ELEMENT_ASSET,
        }


@dataclass(frozen=True)
class LockOperation(AtomicOperation):
    """Lock an element to prevent modifications."""

    def __init__(self, element_id: UUID):
        object.__setattr__(self, "operation_type", OperationType.LOCK)
        object.__setattr__(self, "target_element_id", element_id)
        object.__setattr__(self, "params", {})


@dataclass(frozen=True)
class UnlockOperation(AtomicOperation):
    """Unlock an element to allow modifications."""

    def __init__(self, element_id: UUID):
        object.__setattr__(self, "operation_type", OperationType.UNLOCK)
        object.__setattr__(self, "target_element_id", element_id)
        object.__setattr__(self, "params", {})


@dataclass(frozen=True)
class MoveOperation(AtomicOperation):
    """Move an element to a new position."""

    def __init__(self, element_id: UUID, position: str, preserve_size: bool = True):
        object.__setattr__(self, "operation_type", OperationType.MOVE)
        object.__setattr__(self, "target_element_id", element_id)
        object.__setattr__(self, "params", {
            "position": position,
            "preserve_size": preserve_size,
        })


@dataclass(frozen=True)
class ResizeOperation(AtomicOperation):
    """Resize an element."""

    def __init__(self, element_id: UUID, scale_factor: float):
        object.__setattr__(self, "operation_type", OperationType.RESIZE)
        object.__setattr__(self, "target_element_id", element_id)
        object.__setattr__(self, "params", {"scale_factor": scale_factor})


@dataclass(frozen=True)
class ChangeLayoutOperation(AtomicOperation):
    """Change the slide layout family."""

    def __init__(self, layout_family: LayoutFamily):
        object.__setattr__(self, "operation_type", OperationType.CHANGE_LAYOUT)
        object.__setattr__(self, "target_element_id", None)
        object.__setattr__(self, "params", {"layout_family": layout_family})


@dataclass(frozen=True)
class ReduceTextOperation(AtomicOperation):
    """Reduce text content in an element."""

    def __init__(self, element_id: UUID | None, reduce_lines: int | None = None):
        object.__setattr__(self, "operation_type", OperationType.REDUCE_TEXT)
        object.__setattr__(self, "target_element_id", element_id)
        params = {}
        if reduce_lines is not None:
            params["reduce_lines"] = reduce_lines
        object.__setattr__(self, "params", params)


@dataclass(frozen=True)
class EnlargeHeroOperation(AtomicOperation):
    """Enlarge the hero/main visual element."""

    def __init__(self, scale_factor: float = 1.3):
        object.__setattr__(self, "operation_type", OperationType.ENLARGE_HERO)
        object.__setattr__(self, "target_element_id", None)
        object.__setattr__(self, "params", {"scale_factor": scale_factor})


@dataclass(frozen=True)
class IncreaseWhitespaceOperation(AtomicOperation):
    """Increase whitespace in the layout."""

    def __init__(self):
        object.__setattr__(self, "operation_type", OperationType.INCREASE_WHITESPACE)
        object.__setattr__(self, "target_element_id", None)
        object.__setattr__(self, "params", {})


def intent_to_operation_type(intent: VisualEditIntent) -> OperationType:
    """Map a VisualEditIntent to an OperationType."""
    mapping = {
        VisualEditIntent.ENLARGE_HERO: OperationType.ENLARGE_HERO,
        VisualEditIntent.REDUCE_TEXT: OperationType.REDUCE_TEXT,
        VisualEditIntent.INCREASE_WHITESPACE: OperationType.INCREASE_WHITESPACE,
        VisualEditIntent.CHANGE_LAYOUT: OperationType.CHANGE_LAYOUT,
        VisualEditIntent.SET_HERO_ASSET: OperationType.SET_HERO_ASSET,
        VisualEditIntent.REMOVE_ASSET: OperationType.REMOVE_ASSET,
        VisualEditIntent.LOCK_ELEMENT: OperationType.LOCK,
        VisualEditIntent.UNLOCK_ELEMENT: OperationType.UNLOCK,
        VisualEditIntent.UPDATE_ELEMENT_TEXT: OperationType.UPDATE_ELEMENT_TEXT,
        VisualEditIntent.SET_ELEMENT_ASSET: OperationType.SET_ELEMENT_ASSET,
    }

    if intent not in mapping:
        raise ValueError(f"Cannot map intent {intent} to operation type")

    return mapping[intent]
