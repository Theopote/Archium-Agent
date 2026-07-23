"""Natural-language visual edit intents for Presentation Studio.

Parsers live in ``archium.application.visual.nlp_parser`` (DOM-014).
"""

from __future__ import annotations

from enum import StrEnum


class VisualEditIntent(StrEnum):
    ENLARGE_HERO = "enlarge_hero"
    REDUCE_TEXT = "reduce_text"
    INCREASE_WHITESPACE = "increase_whitespace"
    CHANGE_LAYOUT = "change_layout"
    SET_HERO_ASSET = "set_hero_asset"
    REMOVE_ASSET = "remove_asset"
    LOCK_ELEMENT = "lock_element"
    UNLOCK_ELEMENT = "unlock_element"
    UPDATE_ELEMENT_TEXT = "update_element_text"
    SET_ELEMENT_ASSET = "set_element_asset"
    MOVE_ELEMENT = "move_element"
    RESIZE_ELEMENT = "resize_element"
    RESTORE_PREVIOUS = "restore_previous"


INTENT_USER_LABELS: dict[VisualEditIntent, str] = {
    VisualEditIntent.ENLARGE_HERO: "放大主图",
    VisualEditIntent.REDUCE_TEXT: "减少文字",
    VisualEditIntent.INCREASE_WHITESPACE: "增加留白",
    VisualEditIntent.CHANGE_LAYOUT: "切换版式",
    VisualEditIntent.SET_HERO_ASSET: "设置主图素材",
    VisualEditIntent.REMOVE_ASSET: "移除素材",
    VisualEditIntent.LOCK_ELEMENT: "锁定元素",
    VisualEditIntent.UNLOCK_ELEMENT: "解锁元素",
    VisualEditIntent.UPDATE_ELEMENT_TEXT: "更新元素文字",
    VisualEditIntent.SET_ELEMENT_ASSET: "设置元素素材",
    VisualEditIntent.MOVE_ELEMENT: "移动元素",
    VisualEditIntent.RESIZE_ELEMENT: "缩放元素",
    VisualEditIntent.RESTORE_PREVIOUS: "撤销上一步",
}


def intent_from_preset(preset: str) -> VisualEditIntent | None:
    try:
        return VisualEditIntent(preset)
    except ValueError:
        return None
