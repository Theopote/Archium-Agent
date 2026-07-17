"""Unit tests for graduated slide repair policy."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.slide_repair_policy import (
    _MAX_MESSAGE_LENGTH,
    apply_tiered_layout_repair,
    contains_protected_signal,
    loses_protected_content,
    shorten_repetitive_expression,
    validate_llm_repair,
)
from archium.domain.enums import SlideRepairTier, SlideStatus, SlideType
from archium.domain.slide import SlideSpec


def _slide(**kwargs: object) -> SlideSpec:
    defaults = {
        "presentation_id": uuid4(),
        "chapter_id": "ch1",
        "order": 0,
        "title": "测试页",
        "message": "默认结论",
        "slide_type": SlideType.CONTENT,
        "status": SlideStatus.PLANNED,
    }
    defaults.update(kwargs)
    return SlideSpec(**defaults)  # type: ignore[arg-type]


def test_shorten_repetitive_expression_collapses_duplicates() -> None:
    text = "交通组织交通组织混乱，需要需要优化"
    result = shorten_repetitive_expression(text)
    assert "交通组织交通组织" not in result
    assert "需要需要" not in result


def test_protected_signal_detects_numbers_units_and_risks() -> None:
    assert contains_protected_signal("用地面积 12.5 公顷")
    assert contains_protected_signal("需确认分期决策")
    assert contains_protected_signal("存在人车混行风险")
    assert not contains_protected_signal("总体品质提升")


def test_loses_protected_content_when_number_removed() -> None:
    before = "规划床位 500 张，需确认分期策略"
    after = "需确认分期策略"
    assert loses_protected_content(before, after)


_TIER4_FACT_SEGMENTS = (
    "床位500张",
    "用地12.5公顷",
    "需确认分期决策",
    "存在人车混行风险",
    "急诊通道必须保留",
    "老院区入口落客区不足",
    "三期实施影响门诊运营",
    "货运通道与慢行系统冲突",
    "南侧主入口通行能力不足",
    "北侧卸货流线需重组",
    "住院区后勤通道待优化",
    "消防车道连续性问题",
    "施工期间急诊运营保障要求",
)
_TIER4_LONG_MESSAGE = "，".join(_TIER4_FACT_SEGMENTS)


def test_tier4_when_long_message_contains_numbers() -> None:
    assert len(_TIER4_LONG_MESSAGE) > _MAX_MESSAGE_LENGTH
    slide = _slide(
        message=_TIER4_LONG_MESSAGE,
        key_points=["一般描述"],
    )
    outcome = apply_tiered_layout_repair(slide)
    assert outcome.tier == SlideRepairTier.USER_CONFIRMATION
    assert outcome.requires_manual_confirmation
    assert outcome.slide.message == slide.message


def test_split_overflow_points_instead_of_deleting() -> None:
    slide = SlideSpec.model_construct(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="总体改造方向",
        slide_type=SlideType.CONTENT,
        status=SlideStatus.PLANNED,
        key_points=[f"要点 {index}" for index in range(6)],
    )
    outcome = apply_tiered_layout_repair(slide)
    assert outcome.changed
    assert outcome.tier == SlideRepairTier.SPLIT
    assert len(outcome.slide.key_points) <= 5
    assert outcome.split_slide is not None
    assert len(outcome.split_slide.key_points) >= 1
    assert all(
        point in slide.key_points or point in outcome.split_slide.key_points
        for point in slide.key_points
    )


def test_validate_llm_repair_rejects_protected_point_removal() -> None:
    slide = _slide(
        message="交通需重组",
        key_points=["床位 500 张", "一般说明"],
    )
    valid, reason = validate_llm_repair(
        slide,
        message="交通需重组",
        key_points=["一般说明"],
    )
    assert not valid
    assert "受保护" in reason


def test_rule_repair_shortens_without_dropping_last_point() -> None:
    slide = _slide(
        message="这是一段较长的核心结论用于测试版面密度" * 6,
        key_points=[f"要点描述内容 {index}" * 3 for index in range(4)],
    )
    outcome = apply_tiered_layout_repair(slide)
    assert outcome.changed
    assert outcome.tier in {
        SlideRepairTier.SHORTEN_REPETITION,
        SlideRepairTier.REWRITE,
        SlideRepairTier.SPLIT,
    }
    assert len(outcome.slide.key_points) >= 1
