"""Explainable Next Best Action domain + view helpers."""

from __future__ import annotations

from archium.application.context.nba_explainability import (
    build_explainable_nba_card,
    enrich_next_best_action,
    enrich_next_best_actions,
)
from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType


def test_next_best_action_serializes_explainability_fields() -> None:
    action = NextBestAction(
        action=NextBestActionType.ASK,
        reason="面积冲突",
        why_now="两份资料面积不一致",
        affects=["项目概况页", "经济技术指标表"],
        expected_outcome="确认后按统一口径再生成相关页",
        reversible=True,
        priority=0,
    )
    dumped = action.model_dump(mode="json")
    restored = NextBestAction.model_validate(dumped)
    assert restored.why_now == "两份资料面积不一致"
    assert restored.affects == ["项目概况页", "经济技术指标表"]
    assert restored.expected_outcome.startswith("确认后")
    assert restored.reversible is True


def test_enrich_fills_catalog_defaults_from_reason() -> None:
    raw = NextBestAction(
        action=NextBestActionType.UPLOAD_MATERIALS,
        reason="还缺总图与指标表",
        priority=0,
    )
    enriched = enrich_next_best_action(raw)
    assert enriched.why_now == "还缺总图与指标表"
    assert enriched.affects
    assert enriched.expected_outcome
    assert enriched.reversible is True


def test_build_explainable_nba_card_has_five_surfaces() -> None:
    action = NextBestAction(
        action=NextBestActionType.ASK,
        reason="存在待确认或冲突的关键事实，先澄清再推进",
        why_now="两份资料分别写为 42,000㎡ 和 45,000㎡。",
        affects=["项目概况页", "经济技术指标表"],
        expected_outcome="确认后将重新生成相关页面。",
        reversible=True,
    )
    card = build_explainable_nba_card(action, title="确认建筑面积冲突")
    assert card.title == "确认建筑面积冲突"
    assert "42,000" in card.why_now
    assert "项目概况页" in card.affects
    assert "重新生成" in card.expected_outcome
    assert "撤销" in card.reversible_label


def test_enrich_next_best_actions_preserves_order() -> None:
    actions = enrich_next_best_actions(
        [
            NextBestAction(action=NextBestActionType.RESEARCH, reason="补背景", priority=0),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="比方向",
                priority=1,
            ),
        ]
    )
    assert [item.action for item in actions] == [
        NextBestActionType.RESEARCH,
        NextBestActionType.EXPLORE_DIRECTIONS,
    ]
    assert all(item.why_now for item in actions)
