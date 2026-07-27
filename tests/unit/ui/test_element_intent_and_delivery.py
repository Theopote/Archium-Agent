"""Unit tests for element intent and delivery review panels."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.export_verdict import ExportVerdict, ExportVerdictStatus
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.ui.delivery.delivery_review_panel import (
    build_delivery_checklist,
    estimate_delivery_quality_score,
)
from archium.ui.studio.element_intent_panel import build_element_intent_actions
from archium.ui.studio_service import StudioPresentationContext
from archium.ui.visual_service import PresentationVisualSnapshot, SlideVisualSnapshot


def _hero_element(*, width: float = 2.0, height: float = 1.5) -> LayoutElement:
    return LayoutElement(
        id="hero-1",
        role=LayoutElementRole.HERO_VISUAL,
        content_type=LayoutContentType.IMAGE,
        x=1.0,
        y=1.0,
        width=width,
        height=height,
    )


def test_build_element_intent_suggests_expand_small_hero() -> None:
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        visual_intent_id=uuid4(),
        design_system_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[_hero_element(width=1.0, height=1.0)],
    )
    slide = SlideSpec(
        id=slide_id,
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="封面",
        message="x",
    )
    snapshot = SlideVisualSnapshot(
        slide=slide,
        visual_intent=None,
        layout_plan=plan,
    )
    actions = build_element_intent_actions(snapshot, plan.elements[0])
    assert any("15%" in action.label or "扩大" in action.label for action in actions)


def test_build_element_intent_suggests_shorten_long_title() -> None:
    slide_id = uuid4()
    element = LayoutElement(
        id="title-1",
        role=LayoutElementRole.TITLE,
        content_type=LayoutContentType.TEXT,
        x=1.0,
        y=1.0,
        width=8.0,
        height=1.0,
        text_content="A" * 50,
    )
    plan = LayoutPlan(
        slide_id=slide_id,
        visual_intent_id=uuid4(),
        design_system_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[element],
    )
    slide = SlideSpec(
        id=slide_id,
        presentation_id=uuid4(),
        chapter_id="ch-1",
        order=0,
        title="封面",
        message="x",
    )
    snapshot = SlideVisualSnapshot(slide=slide, visual_intent=None, layout_plan=plan)
    actions = build_element_intent_actions(snapshot, element)
    assert any("压缩" in action.label for action in actions)


def test_delivery_checklist_and_quality_score() -> None:
    project_id = uuid4()
    context = StudioPresentationContext(
        project=Project(name="Demo"),
        presentation=Presentation(project_id=project_id, title="Deck"),
        snapshot=PresentationVisualSnapshot(presentation_id=uuid4()),
        ready_for_export=True,
        slide_count=4,
        layout_ready_count=4,
        preview_ready_count=3,
    )
    verdict = ExportVerdict(
        status=ExportVerdictStatus.READY_WITH_WARNINGS,
        warnings=("一项警告",),
        pptx_ready=True,
        pdf_ready=True,
    )
    checklist = build_delivery_checklist(context=context, verdict=verdict)
    labels = {item.label for item in checklist}
    assert "页面版式" in labels
    assert "PPTX 可导出" in labels
    score = estimate_delivery_quality_score(
        context=context,
        verdict=verdict,
        checklist=checklist,
    )
    assert 50 <= score <= 100
