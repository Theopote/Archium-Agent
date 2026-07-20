"""Unit tests for layout element lock scopes and edit guards."""

from __future__ import annotations

import pytest
from archium.domain.visual.element_lock import (
    ElementEditOperation,
    ElementLockedError,
    ElementLockScope,
    assert_element_editable,
    canvas_geometry_locked,
    effective_lock_scopes,
    element_is_editable,
    is_drawing_element,
)
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.domain.visual.layout import LayoutElement


def _element(
    *,
    locked: bool = False,
    lock_scopes: list[ElementLockScope] | None = None,
    content_type: LayoutContentType = LayoutContentType.TEXT,
    role: LayoutElementRole = LayoutElementRole.TITLE,
) -> LayoutElement:
    return LayoutElement(
        id="title",
        role=role,
        content_type=content_type,
        text_content="标题",
        x=1.0,
        y=1.0,
        width=8.0,
        height=0.8,
        locked=locked,
        lock_scopes=list(lock_scopes or []),
    )


def test_unlocked_element_allows_all_operations() -> None:
    element = _element()
    for operation in ElementEditOperation:
        assert_element_editable(element, operation)


def test_bool_locked_blocks_content_and_asset_edits() -> None:
    element = _element(locked=True)
    assert effective_lock_scopes(element) == {
        ElementLockScope.POSITION,
        ElementLockScope.SIZE,
        ElementLockScope.CONTENT,
        ElementLockScope.ASSET,
        ElementLockScope.STYLE,
    }
    with pytest.raises(ElementLockedError, match="更新文字"):
        assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)
    with pytest.raises(ElementLockedError, match="替换素材"):
        assert_element_editable(element, ElementEditOperation.SET_ASSET)


def test_partial_lock_scopes_only_block_matching_operations() -> None:
    element = _element(locked=True, lock_scopes=[ElementLockScope.CONTENT])
    assert_element_editable(element, ElementEditOperation.SET_ASSET)
    assert not element_is_editable(element, ElementEditOperation.UPDATE_TEXT)
    with pytest.raises(ElementLockedError):
        assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)


def test_lock_toggle_always_allowed() -> None:
    element = _element(locked=True)
    assert_element_editable(element, ElementEditOperation.LOCK_TOGGLE)


def test_drawing_element_blocks_move_and_resize_even_when_unlocked() -> None:
    element = _element(
        locked=False,
        content_type=LayoutContentType.DRAWING,
        role=LayoutElementRole.HERO_VISUAL,
    )
    assert is_drawing_element(element)
    assert canvas_geometry_locked(element)
    assert_element_editable(element, ElementEditOperation.UPDATE_TEXT)
    with pytest.raises(ElementLockedError, match="图纸元素"):
        assert_element_editable(element, ElementEditOperation.MOVE)
    with pytest.raises(ElementLockedError, match="图纸元素"):
        assert_element_editable(element, ElementEditOperation.RESIZE)


def test_content_lock_does_not_lock_canvas_geometry() -> None:
    element = _element(locked=True, lock_scopes=[ElementLockScope.CONTENT])
    assert canvas_geometry_locked(element) is False
