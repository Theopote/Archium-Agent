"""Unit tests for entry IntentClassifierService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.intent_classifier_service import IntentClassifierService
from archium.domain.intent.entry_intent import EntryOrientation
from archium.exceptions import WorkflowError
from archium.infrastructure.llm.entry_intent_schemas import EntryIntentDraft


def test_classify_concept_orientation() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = EntryIntentDraft(
        orientation="concept_exploration",
        confidence=0.82,
        rationale="以一句话想法与地点为主，资料尚未形成。",
        suggested_next="进入概念探索，推演方向后再补资料。",
    )
    result = IntentClassifierService(llm).classify(
        "想在秦岭做一个禅意文化中心，地点大概在山脚下"
    )
    assert result.orientation == EntryOrientation.CONCEPT_EXPLORATION
    assert result.confidence == pytest.approx(0.82)
    assert not result.needs_confirmation
    assert "概念" in result.suggested_next or "方向" in result.suggested_next


def test_classify_existing_project_orientation() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = EntryIntentDraft(
        orientation="existing_project",
        confidence=0.9,
        rationale="已有旧总平与照片，需要整理改造汇报。",
        suggested_next="先上传现有资料进入资料路径。",
    )
    result = IntentClassifierService(llm).classify(
        "医院改扩建，手头有旧总平 PDF 和现场照片，要做甲方汇报"
    )
    assert result.orientation == EntryOrientation.EXISTING_PROJECT
    assert result.orientation.to_origin_mode().value == "existing_project"
    assert not result.needs_confirmation


def test_classify_programming_orientation() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = EntryIntentDraft(
        orientation="research_programming",
        confidence=0.77,
        rationale="重点是投资逻辑与功能定位未知项。",
        suggested_next="进入策划与可研任务。",
    )
    result = IntentClassifierService(llm).classify(
        "文旅综合体立项前要和投资人沟通功能配比与回报逻辑"
    )
    assert result.orientation == EntryOrientation.RESEARCH_PROGRAMMING
    assert not result.needs_confirmation


def test_low_confidence_needs_confirmation() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = EntryIntentDraft(
        orientation="concept_exploration",
        confidence=0.4,
        rationale="描述混杂。",
        suggested_next="请确认。",
    )
    result = IntentClassifierService(llm).classify("又有一点图纸又有想法")
    assert result.needs_confirmation
    assert result.confidence < 0.55


def test_classify_llm_failure_degrades() -> None:
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("down")
    result = IntentClassifierService(llm).classify("随便说说")
    assert result.confidence == 0.0
    assert result.needs_confirmation
    assert "手动" in result.rationale or "失败" in result.rationale


def test_classify_unknown_orientation_degrades() -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = EntryIntentDraft(
        orientation="something_else",
        confidence=0.9,
        rationale="x",
        suggested_next="y",
    )
    result = IntentClassifierService(llm).classify("描述")
    assert result.needs_confirmation
    assert result.confidence == 0.0


def test_classify_empty_raises() -> None:
    with pytest.raises(WorkflowError, match="描述"):
        IntentClassifierService(MagicMock()).classify("   ")
