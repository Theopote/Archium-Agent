"""Golden Layer 1: repair → clear issues → four-layer re-review (Beta B8 / QD-006)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from archium.application.presentation_workflow_service import PresentationWorkflowService
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, WorkflowStatus
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.infrastructure.database.repositories import ReviewRepository
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mock_llm import pipeline_mock_selector
from tests.golden.regression.loader import seed_regression_case

pytestmark = pytest.mark.regression

_CASE_A = Path(__file__).resolve().parent / "cases" / "case_a_hospital.json"


def test_golden_repair_clears_issues_and_reruns_content_review(
    db_session: Session,
    test_settings: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B8: after repair, prior OPEN issues are cleared and content review runs again."""
    settings = test_settings.model_copy(  # type: ignore[attr-defined]
        update={
            "slide_repair_enabled": False,
            "slide_repair_max_rounds": 2,
        }
    )
    case, project = seed_regression_case(db_session, _CASE_A)
    mock_llm = MockLLMProvider(selector=pipeline_mock_selector)

    content_passes: list[int] = []
    injected = {"done": False}

    from archium.workflow.nodes.review import ReviewNodesMixin

    original_content = ReviewNodesMixin.run_content_review
    original_layout = ReviewNodesMixin.run_layout_review

    def tracking_content(self: Any, state: dict[str, Any]) -> dict[str, Any]:
        content_passes.append(int(state.get("repair_round", 0)))
        return original_content(self, state)

    def injecting_layout(self: Any, state: dict[str, Any]) -> dict[str, Any]:
        result = original_layout(self, state)
        if injected["done"] or state.get("errors"):
            return result
        slides = self._load_slides_for_export(state)
        if not slides:
            return result
        presentation_id = UUID(str(state["presentation_id"]))
        issue = ReviewRepository(db_session).create(
            ReviewIssue(
                presentation_id=presentation_id,
                slide_id=slides[0].id,
                reviewer_layer=ReviewLayer.LAYOUT,
                category=ReviewCategory.LENGTH,
                severity=ReviewSeverity.MEDIUM,
                rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
                title="页面信息密度过高",
                description="B8 injected density issue for repair loop",
                auto_fixable=True,
            )
        )
        issues = list(result.get("review_issues") or state.get("review_issues") or [])
        issues.append(issue)
        injected["done"] = True
        return {**result, "review_issues": issues}

    monkeypatch.setattr(ReviewNodesMixin, "run_content_review", tracking_content)
    monkeypatch.setattr(ReviewNodesMixin, "run_layout_review", injecting_layout)

    service = PresentationWorkflowService(db_session, mock_llm, settings=settings)
    try:
        result = service.run(
            project.id,
            case.request,
            export_json=True,
            export_marp=False,
            export_presentation_spec=False,
            require_brief_review=False,
            require_storyline_review=False,
            require_outline_review=False,
            require_slides_review=False,
        )
    finally:
        service.close()

    assert result.workflow_run.status == WorkflowStatus.COMPLETED
    assert injected["done"] is True
    assert content_passes.count(0) >= 1
    assert any(round_idx >= 1 for round_idx in content_passes)
    assert int(result.workflow_run.state.get("repair_round", 0)) >= 1

    issues = ReviewRepository(db_session).list_by_presentation(result.presentation.id)
    injected_rows = [
        item for item in issues if "B8 injected density issue" in item.description
    ]
    assert injected_rows
    assert all(item.status.value == "resolved" for item in injected_rows)
