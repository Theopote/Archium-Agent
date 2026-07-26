"""WF-006 / MS-005 — DeliverablePlan approval content hash contract."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.deliverable_planning_service import (
    DeliverablePlanningService,
    deliverable_plan_approval_hash,
    ensure_deliverable_plan_approval_current,
    is_deliverable_plan_approval_current,
    stamp_deliverable_plan_approval,
)
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import ApprovalStatus, DeliverableType
from archium.exceptions import WorkflowError


def _plan(*, selected: bool = True) -> DeliverablePlan:
    return DeliverablePlan(
        project_id=uuid4(),
        mission_id=uuid4(),
        deliverables=[
            PlannedDeliverable(
                id="d1",
                title="概念汇报",
                deliverable_type=DeliverableType.PRESENTATION,
                purpose="汇报概念",
                selected=selected,
                required=True,
            )
        ],
    )


def test_stamp_sets_hash_matching_compute() -> None:
    plan = _plan()
    stamp_deliverable_plan_approval(plan)
    assert plan.approval_status == ApprovalStatus.APPROVED
    assert plan.approval_hash is not None
    assert plan.approval_hash == deliverable_plan_approval_hash(plan)
    assert is_deliverable_plan_approval_current(plan)


def test_invalidate_clears_hash() -> None:
    plan = _plan()
    stamp_deliverable_plan_approval(plan)
    plan.invalidate_approval()
    assert plan.approval_status == ApprovalStatus.DRAFT
    assert plan.approval_hash is None
    assert not is_deliverable_plan_approval_current(plan)


def test_content_tamper_makes_approval_stale() -> None:
    plan = _plan()
    stamp_deliverable_plan_approval(plan)
    # Simulate silent content edit while status left APPROVED (pre-WF-006 bug).
    plan.deliverables[0].title = "被篡改的标题"
    assert plan.approval_status == ApprovalStatus.APPROVED
    assert not is_deliverable_plan_approval_current(plan)
    with pytest.raises(WorkflowError, match="失效"):
        ensure_deliverable_plan_approval_current(plan)


def test_selection_change_changes_hash() -> None:
    plan = _plan(selected=True)
    stamp_deliverable_plan_approval(plan)
    before = plan.approval_hash
    plan.deliverables[0].selected = False
    assert deliverable_plan_approval_hash(plan) != before
