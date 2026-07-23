"""Golden Layer 1: interrupt + continue_after_review (Beta B7 / WF-008)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.application.review_service import PresentationReviewService
from archium.domain.enums import ApprovalStatus, WorkflowStatus
from archium.infrastructure.database.repositories import ReviewRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.assertions import assert_workflow_expectations
from tests.golden.regression.loader import load_regression_case, seed_regression_case

pytestmark = pytest.mark.regression

_CASE_A = (
    Path(__file__).resolve().parent / "cases" / "case_a_hospital.json"
)


def test_golden_interrupt_and_continue_after_brief_review(
    db_session: Session,
    test_settings: object,
) -> None:
    """B7: LangGraph interrupt at brief gate, then continue_after_review to completion."""
    case, project = seed_regression_case(db_session, _CASE_A)
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]

    try:
        first = service.run(
            project.id,
            case.request,
            export_json=True,
            export_marp=False,
            export_presentation_spec=False,
            require_brief_review=True,
            require_storyline_review=False,
            require_outline_review=False,
            require_slides_review=False,
        )
        assert first.awaiting_review
        assert first.brief is not None
        assert first.brief.approval_status == ApprovalStatus.PENDING
        assert first.storyline is None
        assert first.workflow_run.status == WorkflowStatus.AWAITING_REVIEW
        assert first.workflow_run.state.get("review_gate") == "brief"

        PresentationReviewService(db_session).approve_brief(first.brief.id)
        db_session.commit()

        second = service.continue_after_review(first.workflow_run.id)
    finally:
        service.close()

    assert not second.awaiting_review
    assert second.workflow_run.status == WorkflowStatus.COMPLETED
    assert second.brief is not None
    assert second.storyline is not None
    assert len(second.slides) >= int(case.expectations.get("min_slides", 1))

    issues = ReviewRepository(db_session).list_by_presentation(second.presentation.id)
    assert_workflow_expectations(
        expectations=case.expectations,
        result=second,
        issues=issues,
        session=db_session,
        project_id=project.id,
    )


def test_golden_interrupt_continue_case_loads() -> None:
    case = load_regression_case(_CASE_A)
    assert case.id == "case_a_hospital"
