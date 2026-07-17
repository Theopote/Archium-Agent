"""Unit tests for automated presentation review."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.automated_review_service import AutomatedReviewService
from archium.application.chunk_models import ProjectContextBundle
from archium.domain.document import DocumentChunk
from archium.domain.enums import (
    PresentationType,
    ProjectType,
    ReviewCategory,
    ReviewSeverity,
    VisualType,
)
from archium.domain.presentation import Presentation, PresentationBrief
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def presentation_id(db_session: Session) -> object:
    project = ProjectRepository(db_session).create(
        Project(name="Review Project", project_type=ProjectType.HEALTHCARE)
    )
    return PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Review Test")
    ).id


def test_content_review_flags_missing_citation(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=1,
        title="核心问题",
        message="人车混行导致效率低",
    )
    chunk = DocumentChunk(
        document_id=uuid4(),
        project_id=uuid4(),
        chunk_index=0,
        content="交通组织混乱",
    )
    bundle = ProjectContextBundle(text="ctx", chunks=[chunk])

    issues = AutomatedReviewService(db_session).run_content_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
        context_bundle=bundle,
    )

    assert len(issues) == 1
    assert issues[0].category == ReviewCategory.CITATION
    assert ReviewRepository(db_session).list_by_presentation(presentation_id)  # type: ignore[arg-type]


def test_professional_review_flags_missing_visual_asset(
    db_session: Session,
    presentation_id: object,
) -> None:
    slide = SlideSpec(
        presentation_id=presentation_id,  # type: ignore[arg-type]
        chapter_id="ch1",
        order=0,
        title="改造策略",
        message="通过交通重组释放空间",
        visual_requirements=[
            VisualRequirement(type=VisualType.DIAGRAM, description="交通重组示意", required=True)
        ],
    )

    issues = AutomatedReviewService(db_session).run_professional_review(
        presentation_id,  # type: ignore[arg-type]
        [slide],
    )

    assert len(issues) == 1
    assert issues[0].category == ReviewCategory.VISUAL


def test_professional_review_flags_slide_count_drift(
    db_session: Session,
    presentation_id: object,
) -> None:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,  # type: ignore[arg-type]
        title="Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="管理层",
        purpose="决策",
        duration_minutes=20,
        target_slide_count=10,
        core_message="核心",
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=i,
            title=f"页 {i}",
            message="结论",
        )
        for i in range(4)
    ]

    issues = AutomatedReviewService(db_session).run_professional_review(
        presentation_id,  # type: ignore[arg-type]
        slides,
        brief=brief,
    )

    assert any(issue.category == ReviewCategory.STRUCTURE for issue in issues)
    assert any(issue.severity == ReviewSeverity.MEDIUM for issue in issues)
