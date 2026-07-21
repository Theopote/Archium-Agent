"""Unit tests for Slide Intent Card domain helpers."""

from __future__ import annotations

from archium.domain.slide_intent import (
    SlideIntent,
    format_slide_intent_card,
    slide_intents_from_page_instructions,
)
from archium.prompts.slide_planning import build_single_slide_plan_user_prompt


def test_format_slide_intent_card_includes_core_fields() -> None:
    card = format_slide_intent_card(
        SlideIntent(
            order=6,
            page_task="入口交通问题",
            central_conclusion="人车混行是早高峰拥堵和安全风险的主要原因",
            required_evidence=["入口航拍图", "早高峰车流统计"],
            required_assets=["entrance_drone.jpg"],
            forbidden_content=["参考案例图片"],
            expected_layout="photo_evidence_grid",
            notes="证据优先，不做方案展开",
        )
    )
    assert "页面任务：入口交通问题" in card
    assert "中心结论：人车混行是早高峰拥堵和安全风险的主要原因" in card
    assert "入口航拍图" in card
    assert "禁止内容" in card
    assert "photo_evidence_grid" in card


def test_page_instructions_seed_sparse_orders() -> None:
    intents = slide_intents_from_page_instructions(["首页说明", "", "第三页"])
    assert [item.order for item in intents] == [0, 2]
    assert intents[1].notes == "第三页"


def test_single_slide_prompt_includes_intent_card() -> None:
    prompt = build_single_slide_plan_user_prompt(
        slot_chapter_id="ch1",
        slot_order=0,
        deck_position=0,
        deck_total=10,
        slide_context="【当前页面任务】\n标题：入口",
        brief_summary="brief",
        storyline_summary="story",
        intent_card="【页面意图卡】\n页面任务：入口交通问题",
    )
    assert "【页面意图卡】" in prompt
    assert prompt.index("【页面意图卡】") < prompt.index("【Brief 摘要】")
