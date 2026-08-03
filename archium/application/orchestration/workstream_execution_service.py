"""Execute selected WorkstreamPlan items as a dynamic LangGraph."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.application.orchestration.workstream_handlers import SimpleHandlerRuntime
from archium.application.orchestration.workstream_node_registry import (
    compile_workstream_node_specs,
    selected_workstreams,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import WorkflowStatus, WorkstreamStatus
from archium.domain.workflow import WorkflowRun
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.workflow.checkpointer import WorkflowCheckpointerManager
from archium.workflow.workstream_execution_graph import (
    WorkstreamExecutionGraph,
    initial_workstream_execution_state,
)

WORKFLOW_KIND = "workstream_execution"


@dataclass
class WorkstreamExecutionResult:
    workflow_run: WorkflowRun
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)
    presentation_ready: bool = False

    @property
    def succeeded(self) -> bool:
        return self.workflow_run.status == WorkflowStatus.COMPLETED and self.failed == 0


class WorkstreamExecutionService:
    """Compile selected workstreams into a topo-ordered LangGraph and run it."""

    def __init__(
        self,
        session: SessionLike,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        checkpointer_manager: WorkflowCheckpointerManager | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._workflow_runs = WorkflowRunRepository(session)
        self._missions = MissionRepository(session)
        self._owns_checkpointer = checkpointer_manager is None
        self._checkpointer_manager = checkpointer_manager or WorkflowCheckpointerManager(
            self._settings.workflow_checkpoint_path
        )

    def close(self) -> None:
        if self._owns_checkpointer:
            self._checkpointer_manager.close()

    def __del__(self) -> None:
        if getattr(self, "_owns_checkpointer", False):
            with suppress(Exception):
                self.close()

    def run_for_mission(
        self,
        mission_id: UUID,
        workstreams: list[Workstream],
    ) -> WorkstreamExecutionResult:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"Mission {mission_id} not found")
        return self.run(
            project_id=mission.project_id,
            mission_id=mission_id,
            workstreams=workstreams,
        )

    def run(
        self,
        *,
        project_id: UUID,
        mission_id: UUID | None,
        workstreams: list[Workstream],
    ) -> WorkstreamExecutionResult:
        selected = selected_workstreams(workstreams)
        specs = compile_workstream_node_specs(workstreams, selected_only=True)

        run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": WORKFLOW_KIND,
                    "mission_id": str(mission_id) if mission_id else None,
                    "node_count": len(specs),
                },
            )
        )

        if not specs:
            run.status = WorkflowStatus.COMPLETED
            run.state = {
                **run.state,
                "results": [],
                "warnings": ["无已选工作路径，工作路径执行阶段自动完成"],
                "presentation_ready": False,
            }
            run = self._workflow_runs.update(run)
            return WorkstreamExecutionResult(
                workflow_run=run,
                warnings=list(run.state.get("warnings") or []),
            )

        runtime = SimpleHandlerRuntime(
            session=self._session,
            llm=self._llm,
            project_id=project_id,
            mission_id=mission_id,
            settings=self._settings,
        )
        graph = WorkstreamExecutionGraph.from_workstreams(
            runtime,
            workstreams,
            checkpointer=self._checkpointer_manager.saver,
            selected_only=True,
        )
        initial = initial_workstream_execution_state(
            project_id=project_id,
            mission_id=mission_id,
            specs=specs,
        )
        thread_id = f"workstream-exec-{run.id}"
        with self._checkpointer_manager.serialized_execution(thread_id):
            final = graph.invoke(initial, thread_id=thread_id)

        results = list(final.get("results") or [])
        completed = sum(1 for r in results if r.get("status") == "completed")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        failed = sum(1 for r in results if r.get("status") == "failed")
        warnings = list(final.get("warnings") or [])

        for ws in selected:
            match = next(
                (r for r in results if r.get("workstream_id") == str(ws.id)),
                None,
            )
            if match is None:
                continue
            status = match.get("status")
            if status == "completed":
                ws.status = WorkstreamStatus.COMPLETED
            elif status == "skipped":
                ws.status = WorkstreamStatus.SKIPPED
            elif status == "failed":
                ws.status = WorkstreamStatus.IN_PROGRESS
            ws.touch()

        run.status = (
            WorkflowStatus.FAILED if failed and completed == 0 else WorkflowStatus.COMPLETED
        )
        if failed and completed:
            warnings.append(f"{failed} 个工作路径节点失败，其余已完成")
        run.errors = [str(e) for e in (final.get("errors") or [])]
        run.state = {
            **run.state,
            "results": results,
            "warnings": warnings,
            "presentation_ready": bool(final.get("presentation_ready")),
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
        }
        run = self._workflow_runs.update(run)
        return WorkstreamExecutionResult(
            workflow_run=run,
            completed=completed,
            skipped=skipped,
            failed=failed,
            warnings=warnings,
            presentation_ready=bool(final.get("presentation_ready")),
        )
