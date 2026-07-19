"""Element lock scopes and edit guards for layout elements."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from archium.exceptions import WorkflowError

if TYPE_CHECKING:
    from archium.domain.visual.layout import LayoutElement


class ElementLockScope(StrEnum):
    """Granular lock scopes for layout elements."""

    POSITION = "position"
    SIZE = "size"
    CONTENT = "content"
    ASSET = "asset"
    STYLE = "style"
    ALL = "all"


class ElementEditOperation(StrEnum):
    """User-facing or automated operations that may mutate an element."""

    UPDATE_TEXT = "update_text"
    SET_ASSET = "set_asset"
    REMOVE_ASSET = "remove_asset"
    SET_HERO = "set_hero"
    CHANGE_LAYOUT = "change_layout"
    REPLAN = "replan"
    REPAIR_GEOMETRY = "repair_geometry"
    REPAIR_STYLE = "repair_style"
    LOCK_TOGGLE = "lock_toggle"


_INDIVIDUAL_SCOPES = frozenset(
    {
        ElementLockScope.POSITION,
        ElementLockScope.SIZE,
        ElementLockScope.CONTENT,
        ElementLockScope.ASSET,
        ElementLockScope.STYLE,
    }
)

_OPERATION_SCOPES: dict[ElementEditOperation, frozenset[ElementLockScope]] = {
    ElementEditOperation.UPDATE_TEXT: frozenset({ElementLockScope.CONTENT}),
    ElementEditOperation.SET_ASSET: frozenset({ElementLockScope.ASSET}),
    ElementEditOperation.REMOVE_ASSET: frozenset({ElementLockScope.ASSET}),
    ElementEditOperation.SET_HERO: frozenset({ElementLockScope.ASSET}),
    ElementEditOperation.CHANGE_LAYOUT: frozenset(
        {ElementLockScope.POSITION, ElementLockScope.SIZE}
    ),
    ElementEditOperation.REPLAN: frozenset({ElementLockScope.POSITION, ElementLockScope.SIZE}),
    ElementEditOperation.REPAIR_GEOMETRY: frozenset(
        {ElementLockScope.POSITION, ElementLockScope.SIZE}
    ),
    ElementEditOperation.REPAIR_STYLE: frozenset({ElementLockScope.STYLE}),
    ElementEditOperation.LOCK_TOGGLE: frozenset(),
}

_SCOPE_LABELS: dict[ElementLockScope, str] = {
    ElementLockScope.POSITION: "位置",
    ElementLockScope.SIZE: "尺寸",
    ElementLockScope.CONTENT: "文字内容",
    ElementLockScope.ASSET: "素材",
    ElementLockScope.STYLE: "样式",
    ElementLockScope.ALL: "全部",
}

_OPERATION_LABELS: dict[ElementEditOperation, str] = {
    ElementEditOperation.UPDATE_TEXT: "更新文字",
    ElementEditOperation.SET_ASSET: "替换素材",
    ElementEditOperation.REMOVE_ASSET: "移除素材",
    ElementEditOperation.SET_HERO: "设置主图素材",
    ElementEditOperation.CHANGE_LAYOUT: "切换版式",
    ElementEditOperation.REPLAN: "重新排版",
    ElementEditOperation.REPAIR_GEOMETRY: "几何修复",
    ElementEditOperation.REPAIR_STYLE: "样式修复",
    ElementEditOperation.LOCK_TOGGLE: "锁定/解锁",
}


class ElementLockedError(WorkflowError):
    """Raised when an edit violates element lock scopes."""


def effective_lock_scopes(element: LayoutElement) -> frozenset[ElementLockScope]:
    """Return active lock scopes for an element."""
    if not element.locked:
        return frozenset()
    if element.lock_scopes:
        scopes = set(element.lock_scopes)
        if ElementLockScope.ALL in scopes:
            return _INDIVIDUAL_SCOPES
        return frozenset(scopes)
    return _INDIVIDUAL_SCOPES


def element_is_editable(element: LayoutElement, operation: ElementEditOperation) -> bool:
    """Return True when ``operation`` may mutate ``element``."""
    try:
        assert_element_editable(element, operation)
    except ElementLockedError:
        return False
    return True


def assert_element_editable(element: LayoutElement, operation: ElementEditOperation) -> None:
    """Raise when ``operation`` is blocked by the element's active lock scopes."""
    if operation == ElementEditOperation.LOCK_TOGGLE:
        return

    locked = effective_lock_scopes(element)
    if not locked:
        return

    required = _OPERATION_SCOPES.get(operation, frozenset())
    if not required:
        return

    blocked = locked & required
    if not blocked:
        return

    scope_text = "、".join(_SCOPE_LABELS[scope] for scope in sorted(blocked, key=lambda item: item.value))
    operation_text = _OPERATION_LABELS.get(operation, operation.value)
    raise ElementLockedError(
        f"元素 `{element.id}` 已锁定（{scope_text}），无法{operation_text}。"
    )
