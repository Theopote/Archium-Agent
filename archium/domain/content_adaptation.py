"""Content adaptation actions for SlideSpec in Presentation Studio."""

from __future__ import annotations

from enum import StrEnum


class ContentAdaptationAction(StrEnum):
    SHORTEN = "shorten"
    CONVERT_TO_BULLETS = "convert_to_bullets"
    SPLIT_SLIDE = "split_slide"
    PROMOTE_KEY_MESSAGE = "promote_key_message"


ACTION_USER_LABELS: dict[ContentAdaptationAction, str] = {
    ContentAdaptationAction.SHORTEN: "缩短文字",
    ContentAdaptationAction.CONVERT_TO_BULLETS: "转为要点",
    ContentAdaptationAction.SPLIT_SLIDE: "拆分页面",
    ContentAdaptationAction.PROMOTE_KEY_MESSAGE: "突出核心信息",
}

_NL_RULES: list[tuple[ContentAdaptationAction, tuple[str, ...]]] = [
    (ContentAdaptationAction.SHORTEN, ("缩短", "精简", "shorten", "更少文字")),
    (ContentAdaptationAction.CONVERT_TO_BULLETS, ("要点", "bullet", "条目", "转要点")),
    (ContentAdaptationAction.SPLIT_SLIDE, ("拆分", "拆成两页", "split", "分页")),
    (
        ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
        ("突出核心", "核心信息", "promote", "强调结论"),
    ),
]


def parse_content_adaptation_text(text: str) -> ContentAdaptationAction | None:
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None
    for action, keywords in _NL_RULES:
        if any(keyword in normalized for keyword in keywords):
            return action
    return None


def action_from_value(value: str) -> ContentAdaptationAction | None:
    try:
        return ContentAdaptationAction(value)
    except ValueError:
        return None
