"""Layer 1: deterministic workflow regression tests (Mock LLM, inline chunks)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.infrastructure.database.repositories import ReviewRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.artifacts import save_case_artifacts
from tests.golden.assertions import assert_workflow_expectations
from tests.golden.regression.loader import (
    list_regression_case_paths,
    load_regression_case,
    seed_regression_case,
)

pytestmark = pytest.mark.regression


@pytest.mark.parametrize("case_path", list_regression_case_paths(), ids=lambda p: p.stem)
def test_regression_case_workflow(
    db_session: Session,
    test_settings: object,
    case_path: Path,
) -> None:
    case, project = seed_regression_case(db_session, case_path)
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)
    service = PresentationWorkflowService(db_session, mock_llm, settings=test_settings)  # type: ignore[arg-type]

    try:
        result = service.run(
            project.id,
            case.request,
            export_json=True,
            export_marp=False,
            export_presentation_spec=case.export_presentation_spec,
            require_brief_review=False,
            require_storyline_review=False,
            require_outline_review=False,
            require_slides_review=False,
        )
    finally:
        service.close()

    issues = ReviewRepository(db_session).list_by_presentation(result.presentation.id)
    assert_workflow_expectations(
        expectations=case.expectations,
        result=result,
        issues=issues,
        session=db_session,
        project_id=project.id,
    )
    save_case_artifacts(f"regression_{case.id}", result)


def test_regression_manifests_load() -> None:
    paths = list_regression_case_paths()
    assert len(paths) == 4
    ids = {load_regression_case(path).id for path in paths}
    assert ids == {
        "case_a_hospital",
        "case_b_campus",
        "case_c_competition",
        "case_d_full_deck",
    }
