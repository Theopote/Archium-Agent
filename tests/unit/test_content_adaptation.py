"""Unit tests for content adaptation parsing."""

from __future__ import annotations

from archium.application.content_adaptation_heuristics import parse_content_adaptation_text
from archium.domain.content_adaptation import ContentAdaptationAction


def test_parse_shorten_action() -> None:
    assert parse_content_adaptation_text("请缩短这段文字") == ContentAdaptationAction.SHORTEN


def test_parse_convert_to_bullets_action() -> None:
    assert parse_content_adaptation_text("改成要点列表") == ContentAdaptationAction.CONVERT_TO_BULLETS


def test_parse_split_slide_action() -> None:
    assert parse_content_adaptation_text("拆成两页") == ContentAdaptationAction.SPLIT_SLIDE


def test_parse_promote_key_message_action() -> None:
    assert parse_content_adaptation_text("突出核心信息") == ContentAdaptationAction.PROMOTE_KEY_MESSAGE
