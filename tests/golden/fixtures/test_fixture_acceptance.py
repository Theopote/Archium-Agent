"""Layer 2: real fixture acceptance tests (real parsers + cached/mock LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.infrastructure.database.repositories import DocumentRepository, ReviewRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.golden.artifacts import save_case_artifacts
from tests.golden.assertions import assert_fixture_import_expectations, assert_workflow_expectations
from tests.golden.fixtures.llm_cache import load_cached_llm_selector
from tests.golden.fixtures.loader import (
    list_fixture_manifest_paths,
    load_fixture_case,
    seed_fixture_case,
)

pytestmark = pytest.mark.fixture_acceptance


@pytest.mark.parametrize(
    "manifest_path",
    list_fixture_manifest_paths(),
    ids=lambda p: p.stem.replace(".fixture", ""),
)
def test_fixture_acceptance_workflow(
    db_session: Session,
    test_settings: object,
    manifest_path: Path,
    tmp_path: Path,
) -> None:
    case, project, imported_paths = seed_fixture_case(
        db_session,
        manifest_path,
        scratch_dir=tmp_path,
    )
    mock_llm = MockLLMProvider(selector=load_cached_llm_selector(case.id))
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
            require_slides_review=False,
        )
    finally:
        service.close()

    chunks = DocumentRepository(db_session).list_chunks_by_project(project.id)
    min_chunks = int(case.expectations.get("min_imported_chunks", 1))
    assert len(chunks) >= min_chunks, f"Expected parsed chunks from {imported_paths}"
    assert_fixture_import_expectations(
        expectations=case.expectations,
        imported_paths=imported_paths,
    )

    issues = ReviewRepository(db_session).list_by_presentation(result.presentation.id)
    assert_workflow_expectations(
        expectations=case.expectations,
        result=result,
        issues=issues,
        session=db_session,
        project_id=project.id,
    )
    save_case_artifacts(f"fixture_{case.id}", result)


def test_fixture_manifests_cover_all_regression_cases() -> None:
    paths = list_fixture_manifest_paths()
    assert len(paths) == 5
    ids = {load_fixture_case(path).id for path in paths}
    assert ids == {
        "case_a_hospital",
        "case_b_campus",
        "case_c_competition",
        "case_d_full_deck",
        "case_e_real_paths",
    }
