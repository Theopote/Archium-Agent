"""Tests for MockLLMProvider and LLM schemas."""

from __future__ import annotations

import pytest
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.infrastructure.llm.schemas import (
    DiscordClassification,
    FileClassificationPlan,
    RouterPlan,
)


@pytest.fixture
def mock_provider() -> MockLLMProvider:
    return MockLLMProvider(
        text_responses={
            "router": (
                '{"summary": "生成 PPT", "steps": [{"tool": "ppt_generator", '
                '"params": {"topic": "周报", "output_path": "output/a.pptx"}}]}'
            ),
            "classify": '{"report.pdf": "D:/Reports", "photo.jpg": "D:/Images"}',
            "discord": '{"important": true, "summary": "紧急会议通知"}',
        }
    )


def test_mock_generate_text(mock_provider: MockLLMProvider) -> None:
    result = mock_provider.generate_text(
        LLMRequest(system_prompt="router", user_prompt="做一份 PPT")
    )
    assert "summary" in result
    assert len(mock_provider.calls) == 1


def test_mock_router_plan(mock_provider: MockLLMProvider) -> None:
    plan = mock_provider.generate_structured(
        LLMRequest(system_prompt="router", user_prompt="做 PPT"),
        RouterPlan,
    )
    assert plan.summary == "生成 PPT"
    assert plan.steps[0].tool == "ppt_generator"
    assert plan.steps[0].params["topic"] == "周报"


def test_mock_file_classification(mock_provider: MockLLMProvider) -> None:
    plan = mock_provider.generate_structured(
        LLMRequest(system_prompt="classify", user_prompt="分类文件"),
        FileClassificationPlan,
    )
    result = plan.validate_expected_files({"report.pdf", "photo.jpg"})
    assert result["report.pdf"] == "D:/Reports"


def test_mock_discord_classification(mock_provider: MockLLMProvider) -> None:
    result = mock_provider.generate_structured(
        LLMRequest(system_prompt="discord", user_prompt="消息"),
        DiscordClassification,
    )
    assert result.important is True
    assert "会议" in result.summary


def test_router_plan_empty_steps() -> None:
    provider = MockLLMProvider(
        default_text='{"summary": "你好", "steps": []}',
    )
    plan = provider.generate_structured(
        LLMRequest(system_prompt="", user_prompt="你好"),
        RouterPlan,
    )
    assert plan.steps == []
