"""Integration tests for outline approval gating before SlideSpec."""

from __future__ import annotations

from archium.application.outline_service import merge_template_with_storyline
from archium.application.presentation_service import PresentationService
from archium.domain.enums import ApprovalStatus
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
import pytest

from tests.fixtures.mock_llm import pipeline_mock_selector


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(selector=pipeline_mock_selector)


def _seed(db_session: Session) -> tuple[Project, Presentation]:
    project = ProjectRepository(db_session).create(Project(name="Outline Gate"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Gate Test")
    )
    return project, presentation


def test_slide_plan_accepts_approved_outline(db_session: Session, mock_llm: MockLLMProvider) -> None:
    project, presentation = _seed(db_session)
    repo = PresentationRepository(db_session)
    brief = repo.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="改造汇报",
            audience="政府主管部门",
            purpose="老旧建筑改造",
            core_message="提升价值",
            target_slide_count=10,
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = repo.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="改造必要",
            approval_status=ApprovalStatus.APPROVED,
            chapters=[
                Chapter(
                    id="issue",
                    title="空间问题",
                    purpose="问题",
                    key_message="走廊过窄",
                    order=0,
                )
            ],
        )
    )
    outline = merge_template_with_storyline(brief, storyline)
    outline.approve()
    outline = repo.save_outline(outline)

    from archium.config.settings import get_settings

    settings = get_settings()
    service = PresentationService(db_session, mock_llm, settings=settings)
    slides = service.generate_slide_plan(project.id, brief, storyline, outline=outline)
    assert slides
    assert all(slide.presentation_id == presentation.id for slide in slides)
