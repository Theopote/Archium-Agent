"""Content adaptation actions for SlideSpec in Presentation Studio.

Heuristic parsers/suggesters live in
``archium.application.content_adaptation_heuristics`` (DOM-014).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


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


class ContentAdaptationSuggestion(DomainModel):
    """Suggested content adaptation triggered by layout or content heuristics."""

    action: ContentAdaptationAction
    reason: str = Field(min_length=1)
    trigger_rule_codes: list[str] = Field(default_factory=list)
    requires_user_approval: bool = False


def action_from_value(value: str) -> ContentAdaptationAction | None:
    try:
        return ContentAdaptationAction(value)
    except ValueError:
        return None
