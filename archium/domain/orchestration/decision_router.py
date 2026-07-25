"""Decision Router — replan remaining orchestration stages from ProjectContext.

Preserves completed / in-flight stages; replaces only PENDING tail.
Planning-seat logic (not a new Agent).
"""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.orchestration.models import (
    OrchestrationPlan,
    OrchestrationPlanSource,
    OrchestrationStageSpec,
    OrchestrationStageStatus,
)
from archium.domain.orchestration.plan_builder import (
    label_for_stage,
    page_key_for_stage,
    stages_for_recommended_workflow,
)

_TERMINAL = {
    OrchestrationStageStatus.COMPLETED,
    OrchestrationStageStatus.SKIPPED,
    OrchestrationStageStatus.FAILED,
}

_IN_FLIGHT = {
    OrchestrationStageStatus.RUNNING,
    OrchestrationStageStatus.AWAITING_USER,
    OrchestrationStageStatus.AWAITING_REVIEW,
}


@dataclass(frozen=True)
class ReplanDecision:
    """Explain what the Decision Router changed (for run.state / UI)."""

    changed: bool
    reason: str
    previous_pending: tuple[str, ...] = ()
    new_pending: tuple[str, ...] = ()
    workflow: str = ""
    inserted: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "changed": self.changed,
            "reason": self.reason,
            "previous_pending": list(self.previous_pending),
            "new_pending": list(self.new_pending),
            "workflow": self.workflow,
            "inserted": list(self.inserted),
            "removed": list(self.removed),
        }


def replan_from_context(
    plan: OrchestrationPlan,
    *,
    context: ProjectContext | None = None,
    workflow: RecommendedWorkflow | None = None,
) -> tuple[OrchestrationPlan, ReplanDecision]:
    """Rebuild PENDING stages after the locked prefix from fresh Context.

    Rules:
    - Never drop COMPLETED / SKIPPED / FAILED history.
    - Never yank an in-flight stage (RUNNING / AWAITING_*).
    - Replace only the PENDING tail using ``RecommendedWorkflow`` mapping.
    - Skip desired stages already finished or currently in flight.
    """
    target = workflow
    if target is None and context is not None:
        target = context.recommended_workflow
    if target is None:
        return plan, ReplanDecision(changed=False, reason="无可用上下文，保持原计划")

    locked, pending_tail = _split_locked_and_pending(plan)
    previous_pending = tuple(spec.stage.value for spec in pending_tail)

    finished = {spec.stage for spec in locked if spec.status in _TERMINAL}
    in_flight = {spec.stage for spec in locked if spec.status in _IN_FLIGHT}

    desired = list(stages_for_recommended_workflow(target))
    new_tail: list[OrchestrationStageSpec] = []
    for stage in desired:
        if stage in finished or stage in in_flight:
            continue
        new_tail.append(
            OrchestrationStageSpec(
                stage=stage,
                status=OrchestrationStageStatus.PENDING,
                page_key=page_key_for_stage(stage),
                label=label_for_stage(stage),
            )
        )

    new_pending = tuple(spec.stage.value for spec in new_tail)
    if new_pending == previous_pending:
        return plan, ReplanDecision(
            changed=False,
            reason=f"上下文仍建议 {target.value}，剩余阶段不变",
            previous_pending=previous_pending,
            new_pending=new_pending,
            workflow=target.value,
        )

    inserted = tuple(s for s in new_pending if s not in previous_pending)
    removed = tuple(s for s in previous_pending if s not in new_pending)
    rebuilt = list(locked) + new_tail
    new_index = _first_open_index(rebuilt)
    if new_index is None:
        new_index = max(0, len(rebuilt) - 1)

    updated = plan.model_copy(
        update={
            "stages": rebuilt,
            "active_index": new_index,
            "source": OrchestrationPlanSource.CONTEXT_REPLAN,
        }
    )
    updated.touch()
    reason_bits = [f"按上下文重规划为 {target.value}"]
    if context is not None and context.understanding_summary.strip():
        reason_bits.append(context.understanding_summary.strip()[:120])
    if inserted:
        reason_bits.append("插入：" + "、".join(inserted))
    if removed:
        reason_bits.append("移除待办：" + "、".join(removed))
    return updated, ReplanDecision(
        changed=True,
        reason="；".join(reason_bits),
        previous_pending=previous_pending,
        new_pending=new_pending,
        workflow=target.value,
        inserted=inserted,
        removed=removed,
    )


def _split_locked_and_pending(
    plan: OrchestrationPlan,
) -> tuple[list[OrchestrationStageSpec], list[OrchestrationStageSpec]]:
    """Locked = history + current in-flight; pending = replaceable PENDING tail.

    Walk from the start:
    - Keep every terminal stage.
    - Keep the first in-flight stage (and any terminals before it).
    - Everything from the first PENDING at/after active_index that is not yet
      locked becomes the replaceable tail (plus any later PENDING).
    """
    if not plan.stages:
        return [], []

    locked: list[OrchestrationStageSpec] = []
    pending_tail: list[OrchestrationStageSpec] = []
    locking_done = False

    for index, spec in enumerate(plan.stages):
        if locking_done:
            if spec.status == OrchestrationStageStatus.PENDING:
                pending_tail.append(spec)
            elif spec.status in _TERMINAL or spec.status in _IN_FLIGHT:
                # Rare: keep unexpected later history attached to locked
                locked.append(spec)
            else:
                pending_tail.append(spec)
            continue

        if spec.status in _TERMINAL:
            locked.append(spec)
            continue

        if spec.status in _IN_FLIGHT:
            locked.append(spec)
            locking_done = True
            continue

        # PENDING
        if index < plan.active_index:
            # Stale pending before cursor — treat as locked history skip
            locked.append(
                spec.model_copy(update={"status": OrchestrationStageStatus.SKIPPED})
            )
            continue

        # First pending at/after cursor → start replaceable tail
        pending_tail.append(spec)
        locking_done = True

    return locked, pending_tail


def first_open_stage_index(stages: list[OrchestrationStageSpec]) -> int | None:
    for index, spec in enumerate(stages):
        if spec.status not in _TERMINAL:
            return index
    return None


def _first_open_index(stages: list[OrchestrationStageSpec]) -> int | None:
    return first_open_stage_index(stages)
