"""Golden-case regression tests for fixed architectural presentation scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.enums import ReviewLayer, WorkflowStatus
from archium.infrastructure.database.repositories import ReviewRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.artifacts import save_case_artifacts
from tests.golden.loader import (
    conflicting_fact_keys,
    list_golden_case_paths,
    load_golden_case,
    seed_golden_case,
)


@pytest.mark.parametrize("case_path", list_golden_case_paths(), ids=lambda p: p.stem)
def test_golden_case_workflow(
    db_session: Session,
    test_settings: object,
    case_path: Path,
) -> None:
    case, project = seed_golden_case(db_session, case_path)
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
            require_slides_review=False,
        )
    finally:
        service.close()

    expectations = case.expectations
    assert result.workflow_run.status == WorkflowStatus(expectations.get("workflow_status", "completed"))
    assert len(result.slides) >= int(expectations.get("min_slides", 1))

    issues = ReviewRepository(db_session).list_by_presentation(result.presentation.id)
    expected_layers = expectations.get("review_layers", [])
    if expected_layers:
        layers = {issue.reviewer_layer for issue in issues}
        for layer_name in expected_layers:
            assert ReviewLayer(layer_name) in layers

    conflict_keys = expectations.get("fact_conflict_keys", [])
    if conflict_keys:
        detected = conflicting_fact_keys(db_session, project.id)
        for key in conflict_keys:
            assert key in detected

    title_fragments = expectations.get("issue_title_contains_any", [])
    if title_fragments:
        titles = " ".join(issue.title for issue in issues)
        assert any(fragment in titles for fragment in title_fragments)

    section_keywords = expectations.get("required_section_keywords", [])
    if section_keywords:
        combined = " ".join(
            [result.brief.title if result.brief else ""]
            + ([result.storyline.thesis] if result.storyline else [])
            + [chapter.title for chapter in (result.storyline.chapters if result.storyline else [])]
        )
        for keyword in section_keywords:
            assert keyword in combined

    if case.export_presentation_spec:
        spec_path = result.render.spec_path
        assert spec_path is not None
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        layouts = {slide["layout"] for slide in spec.get("slides", [])}
        expected_layouts = set(expectations.get("spec_layouts_any", []))
        if expected_layouts:
            assert layouts & expected_layouts

    save_case_artifacts(case.id, result)


def test_golden_manifests_load() -> None:
    paths = list_golden_case_paths()
    assert len(paths) == 3
    ids = {load_golden_case(path).id for path in paths}
    assert ids == {"case_a_hospital", "case_b_campus", "case_c_competition"}
