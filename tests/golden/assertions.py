"""Shared expectation assertions for golden acceptance layers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from archium.application.fact_ledger_service import FactLedgerService
from archium.application.workflow_models import WorkflowRunResult
from archium.domain.enums import ReviewLayer, VerificationStatus, WorkflowStatus
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

    min_review_issues = expectations.get("min_review_issues")
    if min_review_issues is not None:
        assert len(issues) >= int(min_review_issues)

    conflict_keys = list(expectations.get("fact_conflict_keys", []))
    if conflict_keys:
        detected = conflicting_fact_keys(session, project_id)
        for key in conflict_keys:
            assert key in detected, f"expected conflict key {key!r} in {sorted(detected)}"

    # KN-007 / B9: Fact Ledger visibility (counts + conflicted status).
    min_facts = expectations.get("min_facts")
    min_conflict_count = expectations.get("min_conflict_count")
    require_conflicted_status = bool(expectations.get("require_conflicted_status", False))
    if min_facts is not None or min_conflict_count is not None or require_conflicted_status:
        ledger = FactLedgerService(session).get_ledger(project_id)
        facts = [entry.fact for entry in ledger.entries if entry.fact is not None]
        facts.extend(ledger.extra_facts)
        if min_facts is not None:
            assert len(facts) >= int(min_facts)
        if min_conflict_count is not None:
            assert ledger.conflict_count >= int(min_conflict_count)
        if require_conflicted_status:
            conflicted = {
                fact.key
                for fact in facts
                if fact.verification_status == VerificationStatus.CONFLICTED
            }
            for key in conflict_keys:
                assert key in conflicted, (
                    f"expected {key!r} marked CONFLICTED, got {sorted(conflicted)}"
                )

    title_fragments = expectations.get("issue_title_contains_any", [])
    if title_fragments:
        titles = " ".join(issue.title for issue in issues)
        assert any(fragment in titles for fragment in title_fragments)

    expected_rule_code_groups = expectations.get("issue_rule_code_groups", [])
    if expected_rule_code_groups:
        rule_codes = {issue.rule_code for issue in issues}
        for group in expected_rule_code_groups:
            assert any(rule_code in rule_codes for rule_code in group)

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


def assert_fixture_import_expectations(
    *,
    expectations: dict[str, Any],
    imported_paths: list[Path],
) -> None:
    if expectations.get("require_unicode_paths"):
        assert any(any(ord(char) > 127 for char in str(path)) for path in imported_paths), (
            "Expected at least one imported path with non-ASCII characters"
        )
    if expectations.get("require_spaced_paths"):
        assert any(" " in path.name or " " in str(path.parent) for path in imported_paths), (
            "Expected at least one imported path containing spaces"
        )
