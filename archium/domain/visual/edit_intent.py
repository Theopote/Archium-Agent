"""Natural-language visual edit intents for Presentation Studio."""

from __future__ import annotations

import re
from enum import StrEnum

from archium.domain.visual.enums import LayoutFamily


class VisualEditIntent(StrEnum):
    ENLARGE_HERO = "enlarge_hero"
    REDUCE_TEXT = "reduce_text"
    INCREASE_WHITESPACE = "increase_whitespace"
    CHANGE_LAYOUT = "change_layout"
    SET_HERO_ASSET = "set_hero_asset"
    REMOVE_ASSET = "remove_asset"
    LOCK_ELEMENT = "lock_element"
    UNLOCK_ELEMENT = "unlock_element"
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
    VisualEditIntent.RESTORE_PREVIOUS: "撤销上一步",
}

_NL_RULES: list[tuple[VisualEditIntent, tuple[str, ...]]] = [
    (VisualEditIntent.RESTORE_PREVIOUS, ("撤销", "恢复", "undo", "restore", "上一步")),
    (VisualEditIntent.ENLARGE_HERO, ("放大主图", "放大主视觉", "enlarge hero", "hero bigger")),
    (VisualEditIntent.REDUCE_TEXT, ("减少文字", "精简文字", "reduce text", "less text")),
    (
        VisualEditIntent.INCREASE_WHITESPACE,
        ("增加留白", "更多留白", "more whitespace", "increase whitespace"),
    ),
    (VisualEditIntent.SET_HERO_ASSET, ("设置主图", "设为主图", "set hero", "hero asset")),
    (VisualEditIntent.REMOVE_ASSET, ("移除素材", "删除素材", "remove asset")),
    (VisualEditIntent.UNLOCK_ELEMENT, ("解锁", "unlock element", "unlock")),
    (VisualEditIntent.LOCK_ELEMENT, ("锁定", "lock element", "lock")),
    (VisualEditIntent.CHANGE_LAYOUT, ("切换版式", "换版式", "change layout", "版式", "layout")),
]

_FAMILY_KEYWORDS: dict[str, LayoutFamily] = {
    "主视觉": LayoutFamily.HERO,
    "hero": LayoutFamily.HERO,
    "图纸": LayoutFamily.DRAWING_FOCUS,
    "drawing": LayoutFamily.DRAWING_FOCUS,
    "证据": LayoutFamily.EVIDENCE_BOARD,
    "比较": LayoutFamily.COMPARATIVE_MATRIX,
    "流程": LayoutFamily.PROCESS_NARRATIVE,
    "分析图": LayoutFamily.ANALYTICAL_DIAGRAM,
    "指标": LayoutFamily.METRIC_DASHBOARD,
    "策略": LayoutFamily.STRATEGY_CARDS,
    "文字": LayoutFamily.TEXTUAL_ARGUMENT,
    "混合": LayoutFamily.HYBRID_CANVAS,
}


def parse_natural_language(text: str) -> tuple[VisualEditIntent | None, dict[str, object]]:
    """Map free-text edit requests to a supported intent and optional params."""
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None, {}

    family = _parse_layout_family(normalized)
    if family is not None and any(token in normalized for token in ("版式", "layout", "切换", "换")):
        return VisualEditIntent.CHANGE_LAYOUT, {"layout_family": family}

    for intent, keywords in _NL_RULES:
        if any(keyword in normalized for keyword in keywords):
            params: dict[str, object] = {}
            if intent == VisualEditIntent.CHANGE_LAYOUT:
                family = _parse_layout_family(normalized)
                if family is not None:
                    params["layout_family"] = family
            if intent in {VisualEditIntent.LOCK_ELEMENT, VisualEditIntent.UNLOCK_ELEMENT}:
                element_id = _parse_element_id(normalized)
                if element_id is not None:
                    params["element_id"] = element_id
            return intent, params

    return None, {}


def intent_from_preset(preset: str) -> VisualEditIntent | None:
    try:
        return VisualEditIntent(preset)
    except ValueError:
        return None


def _parse_layout_family(text: str) -> LayoutFamily | None:
    for keyword, family in _FAMILY_KEYWORDS.items():
        if keyword in text:
            return family
    for family in LayoutFamily:
        if family.value in text:
            return family
    return None


def _parse_element_id(text: str) -> str | None:
    quoted = re.search(r"[「\"']([^」\"']+)[」\"']", text)
    if quoted:
        return quoted.group(1).strip()
    for candidate in ("hero", "title", "drawing", "body", "caption"):
        if candidate in text:
            return candidate
    return None
