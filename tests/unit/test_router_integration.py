"""Integration test for main router with Mock LLM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from archium.infrastructure.llm.factory import reset_llm_provider_cache
from archium.infrastructure.llm.mock import MockLLMProvider
from legacy.main import run_instruction


@dataclass(frozen=True)
class _FakeFile:
    name: str
    suffix: str
    path: Path


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
        patch("legacy.main.get_llm_provider", return_value=mock_provider),
        patch("legacy.main.scan_folder", return_value=[]),
    ):
        report = run_instruction("整理 Downloads 文件夹")

    assert report.success is True
    assert "Downloads" in report.summary
    assert report.plan_labels == ["📂 文件管家"]


def test_run_instruction_skips_file_moves_when_not_confirmed() -> None:
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
    fake_file = _FakeFile(name="draft.dwg", suffix=".dwg", path=Path("/tmp/draft.dwg"))

    with (
        patch("legacy.main.get_llm_provider", return_value=mock_provider),
        patch("legacy.main.scan_folder", return_value=[fake_file]),
        patch(
            "legacy.main.classify_files_with_ai",
            return_value={"draft.dwg": "/tmp/Drawings"},
        ),
        patch("legacy.main.move_files") as move_files,
    ):
        report = run_instruction(
            "整理 Downloads 文件夹",
            confirm_file_moves=lambda _folder, _plan: False,
        )

    move_files.assert_not_called()
    assert report.success is False
    assert report.step_results[0].lines[-1] == "已取消文件移动；本地文件未被修改。"


def test_run_instruction_moves_files_when_confirmed() -> None:
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
    fake_file = _FakeFile(name="draft.dwg", suffix=".dwg", path=Path("/tmp/draft.dwg"))

    with (
        patch("legacy.main.get_llm_provider", return_value=mock_provider),
        patch("legacy.main.scan_folder", return_value=[fake_file]),
        patch(
            "legacy.main.classify_files_with_ai",
            return_value={"draft.dwg": "/tmp/Drawings"},
        ),
        patch("legacy.main.move_files", return_value=[]) as move_files,
    ):
        report = run_instruction(
            "整理 Downloads 文件夹",
            confirm_file_moves=lambda _folder, _plan: True,
        )

    move_files.assert_called_once()
    assert report.success is True
