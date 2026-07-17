"""Integration tests for pipeline transaction rollback."""

from __future__ import annotations

import pytest
from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_service import PresentationService
from archium.domain.enums import ProjectType
from archium.domain.project import Project
from archium.exceptions import LLMProviderError, WorkflowError
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.session import create_engine_from_settings, get_session
from archium.infrastructure.llm import LLMRequest, MockLLMProvider


def _failing_after_brief_selector(request: LLMRequest) -> str | None:
    from tests.fixtures.mock_presentation_responses import BRIEF_JSON

    if "生成 PresentationBrief JSON" in request.user_prompt:
        return BRIEF_JSON
    raise LLMProviderError("Simulated storyline failure")


@pytest.fixture
def request_payload() -> PresentationRequest:
    return PresentationRequest(
        title="Rollback Test",
        audience="Test Audience",
        purpose="Verify rollback",
        duration_minutes=10,
        target_slide_count=2,
        core_message="Test message",
    )


def test_run_pipeline_rolls_back_on_failure(
    test_settings: object,
    request_payload: PresentationRequest,
) -> None:
    engine = create_engine_from_settings(test_settings)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    failing_llm = MockLLMProvider(selector=_failing_after_brief_selector)

    with (
        pytest.raises(WorkflowError, match="Presentation pipeline failed"),
        get_session(engine) as session,
    ):
        project = ProjectRepository(session).create(
            Project(name="Rollback Test Project", project_type=ProjectType.HEALTHCARE)
        )
        service = PresentationService(session, failing_llm, settings=test_settings)  # type: ignore[arg-type]
        service.run_pipeline(project.id, request_payload)

    with get_session(engine) as session:
        presentations = PresentationRepository(session).list_by_project(project.id)
        assert presentations == []

    engine.dispose()
