"""Unit tests for Outline–Template co-planning (Phase 5)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.outline_templates import renovation_outline_sections
from archium.application.visual.outline_template_co_planning_service import (
    OutlineTemplateCoPlanningService,
)
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


def _schema(
    *,
    content: ArchitecturalContentType,
    functional: FunctionalSlideType = FunctionalSlideType.CONTENT,
    supports_drawing: bool = False,
    name: str = "schema",
    purpose: str = "传达核心判断",
) -> ArchitecturalContentSchema:
    return ArchitecturalContentSchema(
        name=name,
        page_purpose=purpose,
        functional_type=functional,
        content_type=content,
        supports_drawing=supports_drawing,
        confidence=0.75,
        representative_slide_id="slide_003",
    )


def _outline(sections: list[OutlineSection], title: str = "改造汇报") -> OutlinePlan:
    return OutlinePlan(
        presentation_id=uuid4(),
        title=title,
        thesis="以证据支持改造决策",
        audience="主管部门",
        purpose="汇报改造方案",
        sections=sections,
        target_slide_count=max(1, sum(s.estimated_slide_count for s in sections)),
    )


def test_cover_and_strategy_get_template_editing() -> None:
    outline = _outline(
        [
            OutlineSection(
                id="cover",
                title="封面",
                purpose="确立主题",
                key_message="老改造提升汇报",
                order=0,
                category="intro",
            ),
            OutlineSection(
                id="goals",
                title="总体提升目标",
                purpose="提出策略目标",
                key_message="形成可执行策略",
                order=1,
                category="strategy",
            ),
        ]
    )
    schemas = [
        _schema(
            content=ArchitecturalContentType.COVER_VISUAL,
            functional=FunctionalSlideType.COVER,
            name="封面视觉",
            purpose="封面",
        ),
        _schema(
            content=ArchitecturalContentType.STRATEGY,
            name="策略页",
            purpose="策略原则",
        ),
    ]
    plan = OutlineTemplateCoPlanningService().plan(outline, schemas)
    assert plan.planned_page_count == 2
    by_section = {p.section_id: p for p in plan.page_plans}
    assert by_section["cover"].inferred_functional_type == FunctionalSlideType.COVER
    assert by_section["cover"].fallback_mode == "template_editing"
    assert by_section["goals"].inferred_content_type == ArchitecturalContentType.STRATEGY
    assert by_section["goals"].fallback_mode == "template_editing"
    assert by_section["goals"].schema_id


def test_multi_slide_section_expands_content_pages() -> None:
    outline = _outline(
        [
            OutlineSection(
                id="architecture",
                title="代表性传统建筑",
                purpose="展示建筑价值",
                key_message="保留核心风貌",
                order=0,
                category="heritage",
                estimated_slide_count=2,
                required_assets=["总平面图纸"],
            )
        ]
    )
    schemas = [
        _schema(
            content=ArchitecturalContentType.DRAWING_FOCUS,
            supports_drawing=True,
            name="图纸聚焦",
            purpose="传统空间格局",
        )
    ]
    plan = OutlineTemplateCoPlanningService().plan(outline, schemas)
    assert plan.planned_page_count == 2
    assert {p.page_role for p in plan.page_plans} == {"primary", "overflow"}
    assert all(p.fallback_mode == "template_editing" for p in plan.page_plans)


def test_drawing_required_without_schema_is_manual() -> None:
    outline = _outline(
        [
            OutlineSection(
                id="site",
                title="总平面分析",
                purpose="说明场地",
                key_message="交通冲突",
                order=0,
                category="technical",
                required_assets=["总平面图纸", "剖面图"],
            )
        ]
    )
    schemas = [
        _schema(
            content=ArchitecturalContentType.STRATEGY,
            supports_drawing=False,
            name="纯策略",
            purpose="策略叙述",
        )
    ]
    plan = OutlineTemplateCoPlanningService().plan(outline, schemas)
    assert plan.page_plans[0].fallback_mode == "manual_required"
    assert plan.manual_required_page_ids
    assert plan.page_plans[0].blockers


def test_no_schemas_falls_back_to_free_composition() -> None:
    outline = _outline(
        [
            OutlineSection(
                id="context",
                title="项目背景",
                purpose="说明背景",
                key_message="现状制约",
                order=0,
                category="context",
            )
        ]
    )
    plan = OutlineTemplateCoPlanningService().plan(outline, [])
    assert plan.page_plans[0].fallback_mode == "free_composition"
    assert plan.free_composition_page_ids
    assert any("free_composition" in w for w in plan.warnings)


def test_unmatched_schemas_and_layouts_are_exposed() -> None:
    outline = _outline(
        [
            OutlineSection(
                id="cover",
                title="封面",
                purpose="确立主题",
                key_message="封面",
                order=0,
                category="intro",
            )
        ]
    )
    cover = _schema(
        content=ArchitecturalContentType.COVER_VISUAL,
        functional=FunctionalSlideType.COVER,
        name="封面",
        purpose="封面",
    )
    unused = _schema(
        content=ArchitecturalContentType.METRIC_SUMMARY,
        name="指标页",
        purpose="指标",
    )
    template = ArchitecturalTemplate(
        name="院区模板",
        layouts=[
            ArchitecturalTemplateLayout(
                name="Cover",
                page_index=0,
                page_type=TemplatePageType.COVER,
                slots=[
                    TemplateSlot(
                        id="t1",
                        role=TemplateSlotRole.TITLE,
                        x=0.5,
                        y=0.5,
                        width=9.0,
                        height=1.0,
                    )
                ],
            ),
            ArchitecturalTemplateLayout(
                name="Metric",
                page_index=1,
                page_type=TemplatePageType.METRIC,
                slots=[
                    TemplateSlot(
                        id="m1",
                        role=TemplateSlotRole.METRIC,
                        x=1.0,
                        y=1.0,
                        width=3.0,
                        height=1.5,
                    )
                ],
            ),
        ],
    )
    plan = OutlineTemplateCoPlanningService().plan(
        outline, [cover, unused], template=template
    )
    assert unused.id in plan.unmatched_schema_ids
    assert plan.unmatched_layout_ids  # metric layout unused
    assert plan.page_plans[0].preferred_layout_id == template.layouts[0].id


def test_renovation_outline_produces_mixed_fallback_modes() -> None:
    sections = renovation_outline_sections()[:8]
    outline = _outline(sections, title="老旧建筑改造")
    schemas = [
        _schema(
            content=ArchitecturalContentType.COVER_VISUAL,
            functional=FunctionalSlideType.COVER,
            name="封面",
            purpose="封面",
        ),
        _schema(
            content=ArchitecturalContentType.TEXT_ARGUMENT,
            name="论述",
            purpose="背景论述",
        ),
        _schema(
            content=ArchitecturalContentType.DRAWING_FOCUS,
            supports_drawing=True,
            name="图纸",
            purpose="空间格局",
        ),
        _schema(
            content=ArchitecturalContentType.PHOTO_ANALYSIS,
            name="现状照片",
            purpose="问题照片",
        ),
        _schema(
            content=ArchitecturalContentType.STRATEGY,
            name="策略",
            purpose="提升策略",
        ),
    ]
    plan = OutlineTemplateCoPlanningService().plan(outline, schemas)
    assert plan.planned_page_count >= 8
    assert plan.template_editing_page_ids or plan.free_composition_page_ids
    assert plan.planning_method == "rule_driven_outline_template_v1"
