"""Unit tests for visual edit intent parsing."""

from __future__ import annotations

from archium.domain.visual.edit_intent import VisualEditIntent, parse_natural_language
from archium.domain.visual.enums import LayoutFamily


def test_parse_reduce_text_intent() -> None:
    intent, params = parse_natural_language("请减少文字，突出主图信息")
    assert intent == VisualEditIntent.REDUCE_TEXT
    assert params == {}


def test_parse_change_layout_with_family() -> None:
    intent, params = parse_natural_language("切换到图纸版式")
    assert intent == VisualEditIntent.CHANGE_LAYOUT
    assert params.get("layout_family") == LayoutFamily.DRAWING_FOCUS


def test_parse_restore_intent() -> None:
    intent, _params = parse_natural_language("撤销上一步修改")
    assert intent == VisualEditIntent.RESTORE_PREVIOUS


def test_parse_lock_element_with_id() -> None:
    intent, params = parse_natural_language("锁定 hero 元素")
    assert intent == VisualEditIntent.LOCK_ELEMENT
    assert params.get("element_id") == "hero"
