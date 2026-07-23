"""LangGraph-based visual composition workflow service."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.art_direction_service import ArtDirectionService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import PresentationWorkflowStep, WorkflowStatus
from archium.domain.presentation import Presentation
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.workflow import WorkflowRun
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.logging import get_logger
from archium.workflow.checkpointer import WorkflowCheckpointerManager
from archium.workflow.visual_graph import VisualWorkflowGraph
from archium.workflow.visual_nodes import VisualWorkflowRuntime
from archium.workflow.visual_serialization import (
    restore_visual_artifacts,
    snapshot_visual_state,
)
from archium.workflow.visual_state import VisualWorkflowState, initial_visual_workflow_state

logger = get_logger(__name__, operation="visual_workflow")


@dataclass
class VisualWorkflowResult:
    """Outcome of a visual composition workflow execution."""

    workflow_run: WorkflowRun
    presentation: Presentation | None = None
    design_system: DesignSystem | None = None
    art_direction: ArtDirection | None = None
    slides: list[SlideSpec] = field(default_factory=list)
    layout_plan_ids: list[str] = field(default_factory=list)
    visual_intent_ids: list[str] = field(default_factory=list)
    render_paths: list[str] = field(default_factory=list)
    validation_reports: list[dict[str, Any]] = field(default_factory=list)
    visual_critic_reports: list[dict[str, Any]] = field(default_factory=list)
    deck_qa_report: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors and self.workflow_run.status == WorkflowStatus.COMPLETED

    @property
    def awaiting_review(self) -> bool:
        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW

    @property
    def review_gate(self) -> str | None:
        gate = self.workflow_run.state.get("review_gate")
        return gate if isinstance(gate, str) else None


class VisualWorkflowService:
    """Run ArtDirection → Layout → Render as a persisted LangGraph workflow."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
        checkpointer_manager: WorkflowCheckpointerManager | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._workflow_runs = WorkflowRunRepository(session)
        self._art_directions = ArtDirectionService(session, llm=llm)
        self._owns_checkpointer = checkpointer_manager is None
        self._checkpointer_manager = checkpointer_manager or WorkflowCheckpointerManager(
            self._settings.workflow_checkpoint_path
        )
        self._runtime = VisualWorkflowRuntime(
            session,
            settings=self._settings,
            llm=llm,
        )
        self._graph = VisualWorkflowGraph(
            self._runtime,
            checkpointer=self._checkpointer_manager.saver,
        )

    def close(self) -> None:
        if self._owns_checkpointer:
            self._checkpointer_manager.close()

    def __del__(self) -> None:
        if getattr(self, "_owns_checkpointer", False):
            with suppress(Exception):
                self.close()

    def _invoke_graph(self, *args: object, thread_id: str, **kwargs: object):
        with self._checkpointer_manager.serialized_execution(thread_id):
            return self._graph.invoke(*args, thread_id=thread_id, **kwargs)

    def run(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        require_art_direction_review: bool = True,
        use_llm: bool = False,
        export_pptx: bool = False,
        export_layout_instructions: bool = True,
        candidate_count: int = 3,
        max_repair_rounds: int = 1,
        preferences: VisualPreferences | None = None,
        design_system_id: UUID | None = None,
    ) -> VisualWorkflowResult:
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"Presentation {presentation_id} not found")
        if presentation.project_id != project_id:
            raise WorkflowError("Presentation does not belong to the given project")

        workflow_run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                presentation_id=presentation_id,
                status=WorkflowStatus.RUNNING,
                state={
                    "workflow_kind": "visual_composition",
                    "current_step": PresentationWorkflowStep.INIT.value,
                    "require_art_direction_review": require_art_direction_review,
                    "use_llm": use_llm,
                    "export_pptx": export_pptx,
                    "export_layout_instructions": export_layout_instructions,
                },
            )
        )

        if self._settings.workflow_checkpoint_commit_enabled:
            self._session.commit()

        initial_state = initial_visual_workflow_state(
            project_id=str(project_id),
            presentation_id=str(presentation_id),
            workflow_run_id=str(workflow_run.id),
            require_art_direction_review=require_art_direction_review,
            use_llm=use_llm,
            export_pptx=export_pptx,
            export_layout_instructions=export_layout_instructions,
            candidate_count=candidate_count,
            max_repair_rounds=max_repair_rounds,
            preferences=preferences,
            design_system_id=str(design_system_id) if design_system_id else None,
        )

        try:
            final_state = self._invoke_graph(initial_state, thread_id=str(workflow_run.id))
        except Exception as exc:
            logger.exception("Visual workflow failed: %s", exc)
            workflow_run.errors = [str(exc)]
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.state = snapshot_visual_state(initial_state)
            workflow_run.touch()
            self._workflow_runs.update(workflow_run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(workflow_run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {workflow_run.id} disappeared after execution")
        return self._to_result(refreshed, final_state)

    def result_from_run(self, workflow_run_id: UUID) -> VisualWorkflowResult:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        return self._to_result(run, run.state)

    def continue_after_art_direction_approval(
        self,
        workflow_run_id: UUID,
        *,
        approve: bool = True,
    ) -> VisualWorkflowResult:
        """Approve (optional) ArtDirection and resume a paused visual workflow."""
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is not awaiting review "
                f"(status={run.status.value})"
            )
        if run.state.get("review_gate") == "layout_review":
            return self.continue_after_layout_review(workflow_run_id)

        art_direction_id = run.state.get("art_direction_id")
        if not isinstance(art_direction_id, str):
            raise WorkflowError("Workflow run is missing art_direction_id")

        if approve:
            self._art_directions.approve(UUID(art_direction_id))

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        try:
            final_state = self._invoke_graph(None, thread_id=str(run.id), resume=True)
        except Exception as exc:
            logger.exception("Visual workflow continue-after-approval failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after continuation")
        return self._to_result(refreshed, final_state)

    def continue_after_layout_review(
        self,
        workflow_run_id: UUID,
        *,
        allow_invalid_layout_export: bool = False,
    ) -> VisualWorkflowResult:
        """Resume after layout review gate.

        PPTX export remains blocked while ERROR/CRITICAL issues persist.
        ``allow_invalid_layout_export`` only acknowledges continuing with
        layout-instruction artifacts (never silent PPTX of invalid pages).
        """
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is not awaiting review "
                f"(status={run.status.value})"
            )
        if run.state.get("review_gate") not in {None, "layout_review"}:
            if run.state.get("review_gate") == "art_direction":
                return self.continue_after_art_direction_approval(workflow_run_id)
            raise WorkflowError(
                f"Workflow run {workflow_run_id} is awaiting "
                f"{run.state.get('review_gate')}, not layout_review"
            )

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        try:
            final_state = self._invoke_graph(
                None,
                thread_id=str(run.id),
                resume=True,
                resume_value={
                    "allow_invalid_layout_export": allow_invalid_layout_export,
                },
            )
        except Exception as exc:
            logger.exception("Visual workflow continue-after-layout-review failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after continuation")
        return self._to_result(refreshed, final_state)

    def resume(self, workflow_run_id: UUID) -> VisualWorkflowResult:
        """Resume a paused or failed-but-checkpointed visual workflow."""
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status == WorkflowStatus.COMPLETED:
            return self._to_result(run, run.state)
        if run.status == WorkflowStatus.AWAITING_REVIEW:
            gate = run.state.get("review_gate")
            if gate == "layout_review":
                return self.continue_after_layout_review(workflow_run_id)
            return self.continue_after_art_direction_approval(workflow_run_id)

        restored = restore_visual_artifacts(run.state)
        if run.presentation_id is None or restored.get("presentation_id") is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing presentation_id")

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        initial_state = initial_visual_workflow_state(
            project_id=str(run.project_id),
            presentation_id=str(run.presentation_id),
            workflow_run_id=str(run.id),
            require_art_direction_review=bool(
                restored.get("require_art_direction_review", True)
            ),
            use_llm=bool(restored.get("use_llm", False)),
            export_pptx=bool(restored.get("export_pptx", False)),
            export_layout_instructions=bool(
                restored.get("export_layout_instructions", True)
            ),
            candidate_count=int(restored.get("candidate_count", 3)),
            max_repair_rounds=int(restored.get("max_repair_rounds", 1)),
            preferences=restored.get("preferences"),
            design_system_id=restored.get("design_system_id"),
        )
        initial_state = cast(
            VisualWorkflowState,
            {**initial_state, **restored, "errors": []},
        )

        try:
            final_state = self._invoke_graph(initial_state, thread_id=str(run.id))
        except Exception as exc:
            logger.exception("Visual workflow resume failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after resume")
        return self._to_result(refreshed, final_state)

    def _to_result(
        self,
        run: WorkflowRun,
        state: VisualWorkflowState | dict[str, Any],
    ) -> VisualWorkflowResult:
        # Prefer live graph state; fall back to persisted snapshot.
        if "presentation" in state or "slides" in state:
            live = state
        else:
            live = restore_visual_artifacts(dict(state))

        presentation = live.get("presentation")
        if presentation is None and run.presentation_id is not None:
            presentation = self._presentations.get_presentation(run.presentation_id)

        return VisualWorkflowResult(
            workflow_run=run,
            presentation=presentation if isinstance(presentation, Presentation) else None,
            design_system=live.get("design_system")
            if isinstance(live.get("design_system"), DesignSystem)
            else None,
            art_direction=live.get("art_direction")
            if isinstance(live.get("art_direction"), ArtDirection)
            else None,
            slides=list(live.get("slides") or [])
            if isinstance(live.get("slides"), list)
            else [],
            layout_plan_ids=list(live.get("layout_plan_ids") or []),
            visual_intent_ids=list(live.get("visual_intent_ids") or []),
            render_paths=list(live.get("render_paths") or []),
            validation_reports=list(live.get("validation_reports") or []),
            visual_critic_reports=list(live.get("visual_critic_reports") or []),
            deck_qa_report=live.get("deck_qa_report")
            if isinstance(live.get("deck_qa_report"), dict)
            else None,
            errors=list(run.errors or live.get("errors") or []),
            warnings=list(live.get("warnings") or []),
        )