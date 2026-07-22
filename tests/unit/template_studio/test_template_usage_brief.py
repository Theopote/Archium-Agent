"""Tests for TemplateUsageBrief generation."""

from __future__ import annotations

import json
from pathlib import Path

from archium.application.visual.template_usage_brief_service import (
    TemplateUsageBriefService,
)
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.template_usage_brief import TemplateUsageBrief


def _minimal_template() -> ArchitecturalTemplate:
    return ArchitecturalTemplate(
        name="演示模板",
        source_pptx_path="source.pptx",
        colors=["#1A1A1A", "#F5F5F5", "#C45C26"],
        layouts=[
            ArchitecturalTemplateLayout(
                name="图纸焦点",
                page_index=0,
                density_range=(0.25, 0.55),
                supports_drawing=True,
                slots=[
                    TemplateSlot(
                        id="title",
                        role=TemplateSlotRole.TITLE,
                        x=0.7,
                        y=0.4,
                        width=8.5,
                        height=0.6,
                    ),
                    TemplateSlot(
                        id="drawing",
                        role=TemplateSlotRole.DRAWING,
                        x=0.7,
                        y=1.2,
                        width=8.5,
                        height=3.8,
                        crop_policy="none",
                    ),
                    TemplateSlot(
                        id="deco",
                        role=TemplateSlotRole.DECORATION,
                        x=0.0,
                        y=5.2,
                        width=10.0,
                        height=0.25,
                    ),
                ],
            )
        ],
    )


def test_minimal_template_markdown_has_ten_sections() -> None:
    service = TemplateUsageBriefService()
    brief = service.build_brief(_minimal_template())
    markdown = service.render_markdown(brief)
    for title in TemplateUsageBriefService.section_titles():
        assert f"## {title}" in markdown, title
    assert "design_system=missing" in brief.evidence


def test_json_round_trip(tmp_path: Path) -> None:
    service = TemplateUsageBriefService()
    brief = service.build_brief(_minimal_template())
    paths = service.write_artifacts(tmp_path, brief)
    assert paths["template_usage_brief_md"].is_file()
    assert paths["template_usage_brief_json"].is_file()
    loaded = TemplateUsageBrief.model_validate(
        json.loads(paths["template_usage_brief_json"].read_text(encoding="utf-8"))
    )
    assert loaded.template_name == brief.template_name
    assert loaded.drawing_treatment == brief.drawing_treatment
    assert loaded.forbidden_patterns == brief.forbidden_patterns


def test_drawing_and_forbidden_rules_visible() -> None:
    service = TemplateUsageBriefService()
    brief = service.build_brief(_minimal_template())
    markdown = service.render_markdown(brief)
    assert "contain" in brief.drawing_treatment.lower()
    assert "cover" in brief.drawing_treatment.lower()
    assert any("cover" in item.lower() for item in brief.forbidden_patterns)
    assert "contain" in markdown.lower()
    assert "cover" in markdown.lower()
