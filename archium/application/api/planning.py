"""/planning — workflow runs + planning sessions facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.planning_session import PlanningSession
from archium.domain.workflow import WorkflowRun
from archium.infrastructure.database.repositories import (
    PlanningSessionRepository,
    WorkflowRunRepository,
)


class PlanningApi:
    """Stable planning read/write helpers (no LangGraph orchestration here)."""

    def __init__(self, session: Session) -> None:
        self._runs = WorkflowRunRepository(session)
        self._sessions = PlanningSessionRepository(session)

    def get_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return self._runs.get_by_id(workflow_run_id)

    def update_run(self, run: WorkflowRun) -> WorkflowRun:
        return self._runs.update(run)

    def list_planning_runs(self, project_id: UUID) -> list[WorkflowRun]:
        return self._runs.list_planning_by_project(project_id)

    def list_runs(self, project_id: UUID) -> list[WorkflowRun]:
        return self._runs.list_by_project(project_id)

    def get_session(self, planning_session_id: UUID) -> PlanningSession | None:
        return self._sessions.get_by_id(planning_session_id)

    def get_session_by_run(self, workflow_run_id: UUID) -> PlanningSession | None:
        return self._sessions.get_by_workflow_run_id(workflow_run_id)

    def list_sessions(self, project_id: UUID) -> list[PlanningSession]:
        return self._sessions.list_by_project(project_id)

    def resolve_session(
        self,
        *,
        planning_session_id: UUID | None = None,
        workflow_run_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> PlanningSession | None:
        if planning_session_id is not None:
            return self.get_session(planning_session_id)
        if workflow_run_id is not None:
            return self.get_session_by_run(workflow_run_id)
        if project_id is not None:
            sessions = self.list_sessions(project_id)
            return sessions[0] if sessions else None
        return None

    def resolve_run(
        self,
        *,
        workflow_run_id: UUID | None = None,
        planning_session: PlanningSession | None = None,
        project_id: UUID | None = None,
    ) -> tuple[WorkflowRun | None, PlanningSession | None]:
        run: WorkflowRun | None = None
        if workflow_run_id is not None:
            run = self.get_run(workflow_run_id)
        elif planning_session is not None and planning_session.workflow_run_id is not None:
            run = self.get_run(planning_session.workflow_run_id)
        elif project_id is not None:
            planning_runs = self.list_planning_runs(project_id)
            run = planning_runs[0] if planning_runs else None
            if planning_session is None and run is not None:
                planning_session = self.get_session_by_run(run.id)
        return run, planning_session
