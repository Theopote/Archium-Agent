"""Integration test for main router with Mock LLM."""

from __future__ import annotations

from unittest.mock import patch

from archium.infrastructure.llm.factory import reset_llm_provider_cache
from archium.infrastructure.llm.mock import MockLLMProvider
from main import run_instruction


def test_run_instruction_with_mock_llm() -> None:
    reset_llm_provider_cache()
    mock_provider = MockLLMProvider(
        text_responses={
            "整理": (
                '{"summary": "整理 Downloads", "steps": ['
                '{"tool": "file_manager", "params": {"folder_path": "~/Downloads"}}'
                "]}"
            ),
        }
    )

    with (
        patch("main.get_llm_provider", return_value=mock_provider),
        patch("main.scan_folder", return_value=[]),
    ):
        report = run_instruction("整理 Downloads 文件夹")

    assert report.success is True
    assert "Downloads" in report.summary
    assert report.plan_labels == ["📂 文件管家"]
