"""Tests for TemplateUsageBrief generation, versioning, and consumers."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from archium.application.visual.icon_selection_service import IconSelectionService
from archium.application.visual.image_treatment_planning_service import (
    ImageTreatmentPlanningService,
)
from archium.application.visual.template_usage_brief_context import (
    bind_brief_to_art_direction,
    constraints_from_brief,
)
from archium.application.visual.template_usage_brief_service import (
    TemplateUsageBriefService,
)
from archium.application.visual.visual_critic_service import VisualCriticService
from archium.domain.enums import ApprovalStatus
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.enums import (
    ImageFit,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
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
    assert f"brief_id: `{brief.id}`" in markdown
    assert f"brief_version: `{brief.version}`" in markdown


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
    assert loaded.id == brief.id
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


def test_constraints_and_art_direction_binding() -> None:
    brief = TemplateUsageBriefService().build_brief(_minimal_template())
    constraints = constraints_from_brief(brief)
    assert constraints.brief_id == brief.id
    assert constraints.drawing_fit_must_contain
    assert constraints.forbid_drawing_cover_crop

    art = ArtDirection(
        project_id=uuid4(),
        concept_name="测试",
        rationale="绑定 Brief",
        palette_strategy="中性",
        typography_strategy="层级清晰",
        grid_strategy="12栏",
        image_strategy="照片统一",
        drawing_strategy="图纸 contain",
        diagram_strategy="线稿",
        annotation_strategy="细线",
        cover_strategy="大标题",
        section_strategy="简洁",
        content_strategy="一页一结论",
        closing_strategy="行动号召",
        pacing_strategy="证据与策略交替",
        approval_status=ApprovalStatus.DRAFT,
    )
    bound = bind_brief_to_art_direction(art, brief)
    assert bound.template_usage_brief_id == brief.id
    assert bound.template_usage_brief_version == brief.version
    # Re-induction creates a new brief id; old ArtDirection keeps the old pointer.
    newer = brief.model_copy(update={"id": uuid4(), "version": brief.version + 1})
    assert bound.template_usage_brief_id != newer.id


def test_image_treatment_planning_uses_brief() -> None:
    brief = TemplateUsageBriefService().build_brief(_minimal_template())
    plan = ImageTreatmentPlanningService().plan(
        content_type=VisualContentType.SITE_PLAN,
        brief=brief,
    )
    assert plan.fit_mode == ImageFit.CONTAIN
    assert plan.forbid_cover_crop is True
    assert plan.template_usage_brief_id == str(brief.id)
    assert plan.template_usage_brief_version == brief.version


def test_icon_selection_records_brief_ref() -> None:
    brief = TemplateUsageBriefService().build_brief(_minimal_template())
    result = IconSelectionService().select("pedestrian", brief=brief)
    assert result.template_usage_brief_id == str(brief.id)
    assert result.template_usage_brief_version == brief.version
    assert result.preferred_style == brief.preferred_icon_style


def test_visual_critic_flags_brief_cover_violation() -> None:
    brief = TemplateUsageBriefService().build_brief(_minimal_template())
    plan = LayoutPlan(
        slide_id=uuid4(),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="drawing",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.5,
                y=1.0,
                width=8.0,
                height=3.5,
                z_index=1,
                fit_mode=ImageFit.COVER,
            )
        ],
    )
    report = VisualCriticService().evaluate_plan(plan, usage_brief=brief)
    assert any(f.rule_code == "CRITIC.TEMPLATE_BRIEF_VIOLATION" for f in report.findings)
