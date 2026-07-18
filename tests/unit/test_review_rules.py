"""Tests for stable review rule codes and repair strategy mapping."""

from __future__ import annotations

from archium.domain.review_rules import (
    ReviewRepairStrategy,
    ReviewRuleCode,
    is_auto_fixable_rule,
    repair_strategy_for_rule,
    resolve_rule_code_from_title,
)


def test_resolve_rule_code_from_title_maps_legacy_display_title() -> None:
    assert (
        resolve_rule_code_from_title("缺少引用来源")
        == ReviewRuleCode.EVIDENCE_MISSING_CITATION
    )
    assert resolve_rule_code_from_title("未知标题") == ReviewRuleCode.LEGACY_UNSPECIFIED


def test_repair_strategy_for_rule_maps_layout_and_content() -> None:
    assert (
        repair_strategy_for_rule(ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY)
        == ReviewRepairStrategy.TIERED_LAYOUT
    )
    assert (
        repair_strategy_for_rule(ReviewRuleCode.CONTENT_MISSING_MESSAGE)
        == ReviewRepairStrategy.LLM_CONTENT
    )
    assert (
        repair_strategy_for_rule(ReviewRuleCode.LAYOUT_MANUAL_LAYOUT_CONFIRMATION)
        == ReviewRepairStrategy.MANUAL
    )
    assert repair_strategy_for_rule(ReviewRuleCode.ARCH_SLIDE_COUNT_DEVIATION) == ReviewRepairStrategy.NONE


def test_is_auto_fixable_rule_only_for_tiered_layout_rules() -> None:
    assert is_auto_fixable_rule(ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS) is True
    assert is_auto_fixable_rule(ReviewRuleCode.CONTENT_MISSING_MESSAGE) is False
