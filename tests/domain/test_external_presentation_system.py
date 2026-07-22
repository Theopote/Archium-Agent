"""Tests for ExternalPresentationSystem domain model."""

from __future__ import annotations

from archium.domain.external_presentation_system import (
    ExternalPresentationSystem,
    RELEVANCE_LABELS_ZH,
)


def test_capability_badges() -> None:
    system = ExternalPresentationSystem(
        id="demo",
        name="Demo",
        editable_pptx=True,
        agentic_workflow=True,
        document_grounding=True,
    )
    badges = system.capability_badges()
    assert "原生 PPTX" in badges
    assert "Agent 工作流" in badges


def test_summary_lines_zh() -> None:
    system = ExternalPresentationSystem(
        id="demo",
        name="Demo System",
        archium_relevance="adopt",
        category="open_source",
        input_modes=["文档"],
        output_formats=["PPTX"],
    )
    lines = system.summary_lines_zh()
    assert RELEVANCE_LABELS_ZH["adopt"] in lines[0]
    assert any("输入" in line for line in lines)
