"""Unit tests for content adaptation suggestion heuristics."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.content_adaptation import (
    ContentAdaptationAction,
    suggest_content_adaptations,
)
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.validation import (
    LAYOUT_TEXT_OVERFLOW,
    LayoutValidationIssue,
    LayoutValidationReport,
)


def _slide(**overrides: object) -> SlideSpec:
    defaults: dict[str, object] = {
        "presentation_id": uuid4(),
        "chapter_id": "ch1",
        "order": 0,
        "title": "测试页",
        "message": "这是一段较长的核心信息，用于测试内容适配建议。",
        "slide_type": SlideType.CONTENT,
        "key_points": ["要点一", "要点二", "要点三", "要点四", "要点五"],
    }
    defaults.update(overrides)
    return SlideSpec(**defaults)  # type: ignore[arg-type]


def test_suggest_shorten_on_text_overflow() -> None:
    report = LayoutValidationReport(
        score=0.7,
        issues=[
            LayoutValidationIssue(
                rule_code=LAYOUT_TEXT_OVERFLOW,
                severity=LayoutIssueSeverity.ERROR,
                message="title overflow",
            )
        ],
    )
    suggestions = suggest_content_adaptations(_slide(), layout_report=report)
    actions = {item.action for item in suggestions}
    assert ContentAdaptationAction.SHORTEN in actions
    assert ContentAdaptationAction.CONVERT_TO_BULLETS in actions


def test_suggest_split_for_dense_slide() -> None:
    suggestions = suggest_content_adaptations(_slide())
    actions = {item.action for item in suggestions}
    assert ContentAdaptationAction.SPLIT_SLIDE in actions
