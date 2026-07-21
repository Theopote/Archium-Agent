"""Unit tests for per-page SlidePlanner generation."""

from __future__ import annotations

from uuid import UUID

import pytest
from archium.agents.slide_planner import SlidePlanner
from archium.config.settings import Settings
from archium.domain.enums import PresentationType
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository, PresentationRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_llm import pipeline_mock_selector


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(selector=pipeline_mock_selector)


@pytest.fixture
def seeded_presentation(db_session: Session) -> tuple[UUID, UUID]:
    project = ProjectRepository(db_session).create(Project(name="Per-page planner"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="Test deck")
    )
    return project.id, presentation.id


def test_slide_planner_per_page_invokes_llm_per_slot(
    db_session: Session,
    mock_llm: MockLLMProvider,
    seeded_presentation: tuple[UUID, UUID],
) -> None:
    project_id, presentation_id = seeded_presentation
    brief = PresentationBrief(
        project_id=project_id,
        presentation_id=presentation_id,
        title="老院区更新",
        audience="院领导",
        purpose="决策",
        core_message="改善交通",
        target_slide_count=4,
        presentation_type=PresentationType.CLIENT_REVIEW,
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="交通重组",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            ),
            Chapter(
                id="ch2",
                title="策略",
                purpose="方案",
                key_message="环形车道",
                order=1,
                estimated_slide_count=2,
            ),
        ],
    )
    settings = Settings(
        _env_file=None,
        slide_per_page_generation=True,
        retrieval_enabled=False,
    )
    planner = SlidePlanner(db_session, mock_llm, settings=settings)
    slides = planner.generate(
        project_id,
        brief,
        storyline,
        replace_existing=False,
    )

    assert len(slides) == 4
    assert len(mock_llm.calls) == 4
    assert all(call.user_prompt.find("生成单页 SlideSpec JSON") >= 0 for call in mock_llm.calls)
    assert all("【当前页面任务】" in call.user_prompt for call in mock_llm.calls)


def test_slide_planner_batch_mode_single_call(
    db_session: Session,
    mock_llm: MockLLMProvider,
    seeded_presentation: tuple[UUID, UUID],
) -> None:
    project_id, presentation_id = seeded_presentation
    brief = PresentationBrief(
        project_id=project_id,
        presentation_id=presentation_id,
        title="老院区更新",
        audience="院领导",
        purpose="决策",
        core_message="改善交通",
        target_slide_count=4,
        presentation_type=PresentationType.CLIENT_REVIEW,
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="交通重组",
        chapters=[
            Chapter(
                id="ch1",
                title="现状",
                purpose="问题",
                key_message="人车混行",
                order=0,
                estimated_slide_count=2,
            ),
        ],
    )
    settings = Settings(
        _env_file=None,
        slide_per_page_generation=False,
        retrieval_enabled=False,
    )
    planner = SlidePlanner(db_session, mock_llm, settings=settings)
    slides = planner.generate(
        project_id,
        brief,
        storyline,
        replace_existing=False,
    )

    assert len(slides) == 4
    assert len(mock_llm.calls) == 1
    assert "SlidePlan JSON" in mock_llm.calls[0].user_prompt
