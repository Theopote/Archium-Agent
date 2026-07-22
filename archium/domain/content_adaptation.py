"""Content adaptation actions for SlideSpec in Presentation Studio."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.slide import SlideSpec
from archium.domain.visual.slide_capacity_budget import (
    CAPACITY_OVERLOAD_RULE,
    SlideCapacityBudget,
)
from archium.domain.visual.validation import (
    LAYOUT_EXCESSIVE_DENSITY,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_TEXT_OVERFLOW,
    LayoutValidationReport,
)


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


_NL_RULES: list[tuple[ContentAdaptationAction, tuple[str, ...]]] = [
    (ContentAdaptationAction.SHORTEN, ("缩短", "精简", "shorten", "更少文字")),
    (ContentAdaptationAction.CONVERT_TO_BULLETS, ("要点", "bullet", "条目", "转要点")),
    (ContentAdaptationAction.SPLIT_SLIDE, ("拆分", "拆成两页", "split", "分页")),
    (
        ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
        ("突出核心", "核心信息", "promote", "强调结论"),
    ),
]

_OVERFLOW_RULES = {
    LAYOUT_TEXT_OVERFLOW,
    LAYOUT_EXCESSIVE_DENSITY,
    LAYOUT_FONT_TOO_SMALL,
}


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


def suggest_content_adaptations(
    slide: SlideSpec,
    *,
    layout_report: LayoutValidationReport | None = None,
    capacity_budget: SlideCapacityBudget | None = None,
) -> list[ContentAdaptationSuggestion]:
    """Analyze slide content and layout issues; return ordered adaptation suggestions."""
    suggestions: list[ContentAdaptationSuggestion] = []
    rule_codes = (
        [issue.rule_code for issue in layout_report.issues] if layout_report is not None else []
    )
    overflow_rules = [code for code in rule_codes if code in _OVERFLOW_RULES]

    if capacity_budget is not None and capacity_budget.is_overloaded:
        if capacity_budget.recommended_action == "split_slide":
            suggestions.append(
                ContentAdaptationSuggestion(
                    action=ContentAdaptationAction.SPLIT_SLIDE,
                    reason=(
                        f"固定画布容量超载（capacity_ratio="
                        f"{capacity_budget.capacity_ratio:.2f}），应拆页而非继续压缩字体。"
                    ),
                    trigger_rule_codes=[CAPACITY_OVERLOAD_RULE],
                    requires_user_approval=True,
                )
            )
            suggestions.append(
                ContentAdaptationSuggestion(
                    action=ContentAdaptationAction.SHORTEN,
                    reason="容量严重超载时也可先缩短正文，再决定是否拆页。",
                    trigger_rule_codes=[CAPACITY_OVERLOAD_RULE],
                )
            )
        else:
            suggestions.append(
                ContentAdaptationSuggestion(
                    action=ContentAdaptationAction.SHORTEN,
                    reason=(
                        f"固定画布容量超载（capacity_ratio="
                        f"{capacity_budget.capacity_ratio:.2f}），"
                        "禁止继续缩字，请先缩短或改写内容。"
                    ),
                    trigger_rule_codes=[CAPACITY_OVERLOAD_RULE],
                )
            )
            suggestions.append(
                ContentAdaptationSuggestion(
                    action=ContentAdaptationAction.CONVERT_TO_BULLETS,
                    reason="将长段落改为要点可降低文字高度预算。",
                    trigger_rule_codes=[CAPACITY_OVERLOAD_RULE],
                )
            )

    if overflow_rules:
        suggestions.append(
            ContentAdaptationSuggestion(
                action=ContentAdaptationAction.SHORTEN,
                reason="版式校验发现文字过多或密度过高，建议先缩短正文。",
                trigger_rule_codes=overflow_rules,
            )
        )
        suggestions.append(
            ContentAdaptationSuggestion(
                action=ContentAdaptationAction.CONVERT_TO_BULLETS,
                reason="将长段落整理为要点，通常能缓解溢出并提升可读性。",
                trigger_rule_codes=overflow_rules,
            )
        )

    bullet_count = len(slide.key_points)
    total_chars = len(slide.message) + sum(len(point) for point in slide.key_points)
    if bullet_count >= 5 or total_chars > 420:
        suggestions.append(
            ContentAdaptationSuggestion(
                action=ContentAdaptationAction.SPLIT_SLIDE,
                reason="本页信息点较多，拆成两页可减轻拥挤。",
                trigger_rule_codes=rule_codes,
                requires_user_approval=True,
            )
        )

    if bullet_count >= 3 and len(slide.message) > 96:
        suggestions.append(
            ContentAdaptationSuggestion(
                action=ContentAdaptationAction.PROMOTE_KEY_MESSAGE,
                reason="核心结论被长段落淹没，建议突出一条主信息。",
                trigger_rule_codes=rule_codes,
            )
        )

    if not suggestions and not slide.key_points and len(slide.message) > 120:
        suggestions.append(
            ContentAdaptationSuggestion(
                action=ContentAdaptationAction.CONVERT_TO_BULLETS,
                reason="核心信息较长，整理为要点更利于版式排版。",
            )
        )

    deduped: list[ContentAdaptationSuggestion] = []
    seen: set[ContentAdaptationAction] = set()
    for item in suggestions:
        if item.action in seen:
            continue
        seen.add(item.action)
        deduped.append(item)
    return deduped
