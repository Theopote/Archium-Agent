"""Unit tests for per-slide SlideGenerationContext assembly."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.slide_context_prompt import format_slide_generation_context
from archium.application.slide_generation_context_service import SlideGenerationContextService
from archium.domain.citation import Citation
from archium.domain.enums import SlideType, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation_manuscript import (
    ManuscriptFact,
    ManuscriptSection,
    PresentationManuscript,
)
from archium.domain.slide import SlideSpec


@pytest.fixture
def presentation_id():
    return uuid4()


@pytest.fixture
def project_id():
    return uuid4()


def _slide(
    presentation_id,
    *,
    chapter_id: str = "ch1",
    order: int = 0,
    title: str = "交通现状",
    message: str = "人车混行是院区主要痛点。",
) -> SlideSpec:
    return SlideSpec(
        presentation_id=presentation_id,
        chapter_id=chapter_id,
        order=order,
        title=title,
        message=message,
        slide_type=SlideType.CONTENT,
        key_points=["入口人车交织", "消防通道被占用"],
        source_citations=[
            Citation(
                document_id=uuid4(),
                document_name="任务书.pdf",
                page_number=3,
                quote="人车混行严重",
            )
        ],
    )


def test_build_context_includes_neighbors_and_section(db_session, presentation_id, project_id) -> None:
    slides = [
        _slide(presentation_id, order=0, title="现状", message="交通混乱。"),
        _slide(presentation_id, order=1, title="策略", message="环形车道分流。"),
    ]
    outline = OutlinePlan(
        presentation_id=presentation_id,
        title="汇报",
        thesis="改善交通",
        audience="院领导",
        purpose="决策",
        sections=[
            OutlineSection(
                id="ch1",
                title="现状分析",
                purpose="说明问题",
                key_message="交通组织混乱",
                order=0,
            )
        ],
    )
    manuscript = PresentationManuscript(
        project_id=project_id,
        presentation_id=presentation_id,
        title="手稿",
        project_summary="老院区更新",
        narrative_thesis="通过交通重组改善体验",
        verified_facts=[
            ManuscriptFact(
                statement="用地面积 12.5 公顷",
                source_id="fact-1",
                verified=True,
            ),
            ManuscriptFact(
                statement="环形车道改造案例参考",
                source_id="fact-2",
                verified=False,
            ),
        ],
        sections=[
            ManuscriptSection(
                id="ch1",
                title="现状分析",
                purpose="说明问题",
                argument="交通组织混乱",
                key_points=["人车混行"],
                fact_ids=[],
                order=0,
            )
        ],
    )

    context = SlideGenerationContextService(db_session).build_for_slide(
        slides[1],
        all_slides=slides,
        project_id=project_id,
        manuscript=manuscript,
        outline=outline,
        max_facts=3,
    )

    assert context.previous_slide_summary is not None
    assert "现状" in context.previous_slide_summary
    assert context.next_slide_intent is None
    assert "现状分析" in context.section_summary
    assert context.verified_facts
    assert context.relevant_citations
    assert context.slide_spec.title == "策略"

    prompt = format_slide_generation_context(context)
    assert "【当前页面任务】" in prompt
    assert "【章节背景】" in prompt
    assert "【上一页摘要】" in prompt
    assert "12.5 公顷" in prompt or context.project_facts


def test_project_facts_selected_when_no_manuscript(db_session, presentation_id, project_id) -> None:
    slide = _slide(presentation_id)
    service = SlideGenerationContextService(db_session)
    service._facts.list_by_project = lambda _pid: [  # type: ignore[method-assign]
        ProjectFact(
            project_id=project_id,
            key="site_area",
            label="用地面积",
            value="12.5",
            unit="公顷",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    ]
    service._assets.list_by_project = lambda _pid: []  # type: ignore[method-assign]

    context = service.build_for_slide(
        slide,
        all_slides=[slide],
        project_id=project_id,
        max_facts=2,
    )
    assert context.project_facts
    assert context.project_facts[0].label == "用地面积"
    assert context.estimated_char_count() < 4000
