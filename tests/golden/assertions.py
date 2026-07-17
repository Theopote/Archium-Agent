"""Shared expectation assertions for golden acceptance layers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.workflow_models import WorkflowRunResult
from archium.domain.enums import ReviewLayer, WorkflowStatus
from archium.domain.review import ReviewIssue
from sqlalchemy.orm import Session
from tests.golden.regression.loader import conflicting_fact_keys


def assert_workflow_expectations(
    *,
    expectations: dict[str, Any],
    result: WorkflowRunResult,
    issues: list[ReviewIssue],
    session: Session,
    project_id: UUID,
) -> None:
    assert result.workflow_run.status == WorkflowStatus(
        expectations.get("workflow_status", "completed")
    )
    assert len(result.slides) >= int(expectations.get("min_slides", 1))

    expected_layers = expectations.get("review_layers", [])
    if expected_layers:
        layers = {issue.reviewer_layer for issue in issues}
        for layer_name in expected_layers:
            assert ReviewLayer(layer_name) in layers

    conflict_keys = expectations.get("fact_conflict_keys", [])
    if conflict_keys:
        detected = conflicting_fact_keys(session, project_id)
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

    if expectations.get("export_presentation_spec") or result.render.spec_path:
        spec_path = result.render.spec_path
        assert spec_path is not None
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        layouts = {slide["layout"] for slide in spec.get("slides", [])}
        expected_layouts = set(expectations.get("spec_layouts_any", []))
        if expected_layouts:
            assert layouts & expected_layouts
