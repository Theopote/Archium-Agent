"""Tests for ExternalPresentationSystem domain model."""

from __future__ import annotations

from archium.domain.external_presentation_system import ExternalPresentationSystem


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
    assert "文档接地" in badges


def test_summary_lines_zh() -> None:
    system = ExternalPresentationSystem(
        id="pptagent",
        name="PPTAgent",
        category="research",
        input_modes=["文档"],
        output_formats=["PPTX"],
        archium_relevance="adopt",
    )
    lines = system.summary_lines_zh()
    assert any("PPTAgent" in line for line in lines)
    assert any("采纳" in line for line in lines)
