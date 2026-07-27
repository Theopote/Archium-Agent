"""Product continue-work routing (Topic 07 L1 / UI-007).

Prefers unresolved design ProcessBoard focus and design-side orchestration
stages over the presentation five-stage heuristic.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.orchestration.models import OrchestrationStage, OrchestrationStageStatus
from archium.domain.orchestration.plan_builder import page_key_for_stage
from archium.domain.process import DesignProcessFocus, ProcessPointer

_UNRESOLVED_DESIGN = frozenset(
    {
        DesignProcessFocus.EXPLORING,
        DesignProcessFocus.COMPARING_DIRECTIONS,
    }
)

_DESIGN_ORCH_STAGES = frozenset(
    {
        OrchestrationStage.EXPLORE,
        OrchestrationStage.RESEARCH,
        OrchestrationStage.MISSION_PLANNING,
        OrchestrationStage.WORKSTREAM_EXECUTION,
    }
)


def page_for_unresolved_design(
    session: Session,
    pointer: ProcessPointer,
) -> str | None:
    """Return concept-exploration / project-mission while directions are open."""
    focus = pointer.design_focus()
    if focus not in _UNRESOLVED_DESIGN:
        return None
    if pointer.active_id is not None:
        from archium.infrastructure.database.mission_repositories import MissionRepository

        if MissionRepository(session).get_mission(pointer.active_id) is not None:
            return "project-mission"
    return "concept-exploration"


def page_for_active_design_orchestration(
    session: Session,
    project_id: UUID,
) -> str | None:
    """If orchestration is mid design/mission stages, resume that page."""
    from archium.domain.enums import WorkflowStatus
    from archium.domain.orchestration.models import OrchestrationPlan
    from archium.infrastructure.database.repositories import WorkflowRunRepository

    for run in WorkflowRunRepository(session).list_by_project(project_id):
        if run.state.get("workflow_kind") != "orchestration":
            continue
        if run.status not in {WorkflowStatus.RUNNING, WorkflowStatus.AWAITING_REVIEW}:
            continue
        raw = run.state.get("orchestration_plan")
        if not isinstance(raw, dict):
            continue
        try:
            plan = OrchestrationPlan.model_validate(raw)
        except Exception:
            continue
        stage = plan.active_stage()
        if stage is None or stage.stage not in _DESIGN_ORCH_STAGES:
            continue
        if stage.status in {
            OrchestrationStageStatus.COMPLETED,
            OrchestrationStageStatus.SKIPPED,
            OrchestrationStageStatus.FAILED,
        }:
            continue
        return page_key_for_stage(stage.stage)
    return None


def page_for_starter_draft(
    session: Session,
    project_id: UUID,
    *,
    slide_count: int,
    layout_ready_count: int,
) -> str | None:
    """When genesis seeded slides exist, prefer studio/outline over open exploration."""
    if slide_count <= 0:
        return None
    from archium.application.genesis_starter_service import get_genesis_starter_state

    starter = get_genesis_starter_state(session, project_id)
    if starter is None:
        return None
    if layout_ready_count < slide_count:
        return "edit"
    if starter.page_count > 0:
        return "outline"
    return None


def resolve_continue_work_page_key(
    session: Session,
    project_id: UUID,
    *,
    presentation_stage_id: str,
    slide_count: int = 0,
    layout_ready_count: int = 0,
    actor_id: str | None = None,
) -> str:
    """Single continue-work truth: Ask → design → role → orchestration → NBA → stage.

    Role navigation applies only when ``actor_id`` is explicitly passed.
    Callers that omit it keep the design/orchestration heuristic (tests, tools).
    """
    from archium.application.context.workflow_navigation import workflow_entry_for_project
    from archium.application.design_revise_persistence import load_pending_design_revise
    from archium.application.process.design_process_pointer import build_design_pointer
    from archium.application.role_navigation import resolve_role_navigation

    explicit_actor = (actor_id or "").strip() or None
    role_hint = None
    if explicit_actor is not None:
        role_hint = resolve_role_navigation(
            session,
            project_id,
            actor_id=explicit_actor,
            slide_count=slide_count,
            presentation_stage_id=presentation_stage_id,
        )

    try:
        pending = load_pending_design_revise(session, project_id)
    except Exception:
        pending = None
    if pending is not None:
        if role_hint is not None and not role_hint.can_edit:
            return role_hint.primary_page_key
        try:
            from archium.infrastructure.database.repositories import (
                ConceptDirectionRepository,
            )

            direction_id = UUID(str(pending["direction_id"]))
            direction = ConceptDirectionRepository(session).get(direction_id)
            if direction is not None and direction.mission_id is not None:
                return "project-mission"
        except Exception:
            pass
        return "concept-exploration"

    draft_page = page_for_starter_draft(
        session,
        project_id,
        slide_count=slide_count,
        layout_ready_count=layout_ready_count,
    )
    if draft_page is not None:
        return draft_page

    pointer = build_design_pointer(session, project_id)
    design_page = page_for_unresolved_design(session, pointer)
    if design_page is not None:
        if role_hint is not None and not role_hint.can_edit:
            return role_hint.primary_page_key
        return design_page

    if role_hint is not None and role_hint.is_read_leaning:
        return role_hint.primary_page_key

    orch_page = page_for_active_design_orchestration(session, project_id)
    if orch_page is not None:
        return orch_page

    if slide_count <= 0:
        entry = workflow_entry_for_project(session, project_id)
        if entry is not None and entry.page_key:
            return entry.page_key

    return presentation_stage_id


def design_loop_open(pointer: ProcessPointer) -> bool:
    """True when concept directions are still being explored/compared."""
    return pointer.design_focus() in _UNRESOLVED_DESIGN
