"""Stepper / stage-gate truthfulness — never fake done from navigation index."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.domain.enums import EvidenceAvailability
from archium.ui.pages.flow import (
    _stage_statuses,
    evaluate_stage_gate,
    stage_completion_status,
)
from archium.ui.project_progress_card import ProjectProgressSnapshot


def _empty_snapshot(**overrides: object) -> ProjectProgressSnapshot:
    base = {
        "project_id": uuid4(),
        "project_name": "空项目",
        "presentation_id": None,
        "presentation_title": None,
        "presentation_type": None,
        "document_count": 0,
        "slide_count": 0,
        "layout_ready_count": 0,
        "has_brief": False,
        "ready_for_export": False,
        "updated_at": datetime.now(UTC),
        "outline_approved": False,
        "has_outline": False,
        "evidence_availability": EvidenceAvailability.MISSING,
        "export_blocker_count": 0,
    }
    base.update(overrides)
    return ProjectProgressSnapshot(**base)  # type: ignore[arg-type]


def test_empty_project_stage_completion_is_honest() -> None:
    snap = _empty_snapshot()
    assert stage_completion_status("materials", snap) == "warn"
    assert stage_completion_status("outline", snap) == "todo"
    assert stage_completion_status("generate", snap) == "todo"
    assert stage_completion_status("edit", snap) == "blocked"
    assert stage_completion_status("deliver", snap) == "todo"


def test_opening_deliver_does_not_mark_prior_stages_done() -> None:
    snap = _empty_snapshot()
    statuses = _stage_statuses("deliver", snap)
    assert statuses["materials"] == "warn"
    assert statuses["outline"] == "todo"
    assert statuses["generate"] == "todo"
    assert statuses["edit"] == "blocked"
    # Current page may be highlighted, but must not be faked as done.
    assert statuses["deliver"] != "done"


def test_opening_edit_does_not_mark_materials_done() -> None:
    snap = _empty_snapshot()
    statuses = _stage_statuses("edit", snap)
    assert statuses["materials"] == "warn"
    assert statuses["outline"] == "todo"
    assert statuses["generate"] == "todo"


def test_concept_draft_gate_warns_but_deliver_blocks() -> None:
    snap = _empty_snapshot()
    materials = evaluate_stage_gate("materials", snap)
    assert materials.can_proceed
    assert materials.warnings

    outline = evaluate_stage_gate("outline", snap)
    assert not any("资料" in item for item in outline.blockers)
    assert any("草稿" in item or "资料" in item for item in outline.warnings)

    deliver = evaluate_stage_gate("deliver", snap)
    assert not deliver.can_proceed
    assert deliver.blockers


def test_outline_done_requires_approval() -> None:
    brief_only = _empty_snapshot(has_brief=True)
    assert stage_completion_status("outline", brief_only) == "current"

    generated = _empty_snapshot(has_brief=True, has_outline=True)
    assert stage_completion_status("outline", generated) == "warn"

    approved = _empty_snapshot(has_outline=True, outline_approved=True)
    assert stage_completion_status("outline", approved) == "done"


def test_layout_ready_without_docs_is_warn_not_done_for_deliver() -> None:
    snap = _empty_snapshot(
        ready_for_export=True,
        slide_count=3,
        layout_ready_count=3,
        document_count=0,
        evidence_availability=EvidenceAvailability.MISSING,
    )
    assert stage_completion_status("deliver", snap) == "warn"
    assert not snap.formal_delivery_ready
    assert snap.draft_export_ready


def test_unknown_evidence_blocks_materials_and_deliver() -> None:
    snap = _empty_snapshot(evidence_availability=EvidenceAvailability.UNKNOWN)
    assert stage_completion_status("materials", snap) == "blocked"
    materials = evaluate_stage_gate("materials", snap)
    assert not materials.can_proceed
    deliver = evaluate_stage_gate("deliver", snap)
    assert not deliver.can_proceed
    assert any("无法验证" in item for item in deliver.blockers)
