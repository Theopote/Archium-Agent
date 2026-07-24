"""Unit tests for product-flow stage routing with project origin modes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.domain.enums import EvidenceAvailability, ProjectOriginMode
from archium.ui.project_progress_card import ProjectProgressSnapshot


def _snapshot(**overrides) -> ProjectProgressSnapshot:
    base = dict(
        project_id=uuid4(),
        project_name="测试项目",
        presentation_id=None,
        presentation_title=None,
        presentation_type=None,
        document_count=0,
        slide_count=0,
        layout_ready_count=0,
        has_brief=False,
        ready_for_export=False,
        updated_at=datetime.now(UTC),
        outline_approved=False,
        has_outline=False,
        outline_changes_pending=False,
        design_briefs_approved=False,
        design_briefs_total=0,
        design_briefs_approved_count=0,
        evidence_availability=EvidenceAvailability.MISSING,
        export_blocker_count=0,
        pptx_ready=False,
        pdf_ready=False,
        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
        has_mission_or_task=False,
    )
    base.update(overrides)
    return ProjectProgressSnapshot(**base)


def test_concept_exploration_routes_to_outline_without_documents() -> None:
    snapshot = _snapshot(
        origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        has_mission_or_task=True,
    )
    assert snapshot.current_stage_id == "outline"


def test_research_programming_routes_to_outline_without_documents() -> None:
    snapshot = _snapshot(
        origin_mode=ProjectOriginMode.RESEARCH_PROGRAMMING,
        has_mission_or_task=True,
    )
    assert snapshot.current_stage_id == "outline"


def test_skips_default_clarification_includes_programming() -> None:
    assert ProjectOriginMode.RESEARCH_PROGRAMMING.skips_default_clarification
    assert ProjectOriginMode.CONCEPT_EXPLORATION.skips_default_clarification
    assert not ProjectOriginMode.EXISTING_PROJECT.skips_default_clarification


def test_existing_project_without_docs_but_with_mission_routes_to_outline() -> None:
    snapshot = _snapshot(
        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
        has_mission_or_task=True,
        document_count=0,
    )
    assert snapshot.current_stage_id == "outline"


def test_existing_project_without_docs_or_mission_routes_to_materials() -> None:
    snapshot = _snapshot(
        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
        has_mission_or_task=False,
        document_count=0,
    )
    assert snapshot.current_stage_id == "materials"


def test_existing_project_with_documents_routes_to_outline_when_unapproved() -> None:
    snapshot = _snapshot(
        origin_mode=ProjectOriginMode.EXISTING_PROJECT,
        document_count=2,
        has_mission_or_task=False,
        outline_approved=False,
    )
    assert snapshot.current_stage_id == "outline"
