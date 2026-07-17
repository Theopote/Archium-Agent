"""LangGraph-based presentation workflow service."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.presentation_models import PresentationRequest
from archium.application.review_service import PresentationReviewService
from archium.application.workflow_models import WorkflowRunResult
from archium.config.settings import Settings, get_settings
from archium.domain.enums import WorkflowStatus, WorkflowStep
from archium.domain.render import RenderResult
from archium.domain.workflow import WorkflowRun
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.json_renderer import JsonPresentationRenderer
from archium.logging import get_logger
from archium.workflow.checkpointer import WorkflowCheckpointerManager
from archium.workflow.presentation_graph import PresentationWorkflowGraph
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.serialization import request_to_dict, restore_domain_artifacts, snapshot_state
from archium.workflow.state import PresentationWorkflowState, initial_workflow_state

logger = get_logger(__name__, operation="presentation_workflow")


class PresentationWorkflowService:
    """Run the presentation pipeline as a persisted LangGraph workflow."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        renderer: JsonPresentationRenderer | None = None,
        checkpointer_manager: WorkflowCheckpointerManager | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._runtime = PresentationWorkflowRuntime.create(
            session,
            llm,
            settings=self._settings,
            renderer=renderer,
        )
        self._workflow_runs = WorkflowRunRepository(session)
        self._owns_checkpointer = checkpointer_manager is None
        self._checkpointer_manager = checkpointer_manager or WorkflowCheckpointerManager(
            self._settings.workflow_checkpoint_path
        )
        self._graph = PresentationWorkflowGraph(
            self._runtime,
            checkpointer=self._checkpointer_manager.saver,
        )

    def close(self) -> None:
        """Close the LangGraph SQLite checkpointer connection."""
        self._checkpointer_manager.close()

    def __del__(self) -> None:
        if getattr(self, "_owns_checkpointer", False):
            with suppress(Exception):
                self.close()

    def run(
        self,
        project_id: UUID,
        request: PresentationRequest,
        *,
        export_json: bool = True,
        export_presentation_spec: bool = False,
        export_editable_pptx: bool = False,
        export_marp: bool = False,
        export_pptx: bool = False,
        export_pdf: bool = False,
        export_preview_images: bool | None = None,
        require_brief_review: bool = False,
        require_storyline_review: bool = False,
        require_slides_review: bool = False,
    ) -> WorkflowRunResult:
        presentation = self._runtime.presentation_service.create_presentation(project_id, request)
        resolved_preview_images = (
            export_preview_images
            if export_preview_images is not None
            else export_marp and self._settings.marp_preview_images_enabled
        )
        workflow_run = self._workflow_runs.create(
            WorkflowRun(
                project_id=project_id,
                presentation_id=presentation.id,
                status=WorkflowStatus.RUNNING,
                state={
                    "current_step": WorkflowStep.INIT.value,
                    "request": request_to_dict(request),
                    "export_json": export_json,
                    "export_presentation_spec": export_presentation_spec or export_editable_pptx,
                    "export_editable_pptx": export_editable_pptx,
                    "export_marp": export_marp,
                    "export_pptx": export_pptx,
                    "export_pdf": export_pdf,
                    "export_preview_images": resolved_preview_images,
                    "require_brief_review": require_brief_review,
                    "require_storyline_review": require_storyline_review,
                    "require_slides_review": require_slides_review,
                },
            )
        )

        initial_state = initial_workflow_state(
            project_id=str(project_id),
            presentation_id=str(presentation.id),
            workflow_run_id=str(workflow_run.id),
            request=request,
            presentation=presentation,
            export_json=export_json,
            export_presentation_spec=export_presentation_spec,
            export_editable_pptx=export_editable_pptx,
            export_marp=export_marp,
            export_pptx=export_pptx,
            export_pdf=export_pdf,
            export_preview_images=resolved_preview_images,
            require_brief_review=require_brief_review,
            require_storyline_review=require_storyline_review,
            require_slides_review=require_slides_review,
        )

        try:
            final_state = self._graph.invoke(initial_state, thread_id=str(workflow_run.id))
        except Exception as exc:
            logger.exception("Workflow graph execution failed: %s", exc)
            workflow_run.errors = [str(exc)]
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.state = snapshot_state(initial_state)
            workflow_run.touch()
            self._workflow_runs.update(workflow_run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(workflow_run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {workflow_run.id} disappeared after execution")

        return self._ensure_success(self._to_result(refreshed, final_state))

    def continue_after_review(self, workflow_run_id: UUID) -> WorkflowRunResult:
        """Resume a workflow paused at a LangGraph interrupt for human review."""
        review_service = PresentationReviewService(self._session)
        context = review_service.ensure_can_continue(workflow_run_id)
        run = context.workflow_run
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        try:
            final_state = self._graph.invoke(None, thread_id=str(run.id), resume=True)
        except Exception as exc:
            logger.exception("Workflow continue-after-review failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after continuation")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def resume(self, workflow_run_id: UUID) -> WorkflowRunResult:
        """Re-run or continue a workflow from its LangGraph checkpoint."""
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status == WorkflowStatus.COMPLETED:
            return self._to_result(run, run.state)
        if run.status == WorkflowStatus.AWAITING_REVIEW:
            return self.continue_after_review(workflow_run_id)

        restored = restore_domain_artifacts(run.state)
        request = restored.get("request")
        presentation = restored.get("presentation")
        if request is None or presentation is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} is missing resumable state")

        run.status = WorkflowStatus.RUNNING
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

        initial_state = initial_workflow_state(
            project_id=str(run.project_id),
            presentation_id=str(run.presentation_id),
            workflow_run_id=str(run.id),
            request=request,
            presentation=presentation,
            export_json=bool(run.state.get("export_json", True)),
            export_presentation_spec=bool(run.state.get("export_presentation_spec", False)),
            export_editable_pptx=bool(run.state.get("export_editable_pptx", False)),
            export_marp=bool(run.state.get("export_marp", False)),
            export_pptx=bool(run.state.get("export_pptx", False)),
            export_pdf=bool(run.state.get("export_pdf", False)),
            export_preview_images=bool(run.state.get("export_preview_images", False)),
            require_brief_review=bool(run.state.get("require_brief_review", False)),
            require_storyline_review=bool(run.state.get("require_storyline_review", False)),
            require_slides_review=bool(run.state.get("require_slides_review", False)),
        )
        initial_state = cast(
            PresentationWorkflowState,
            {
                **initial_state,
                **restored,
                "errors": [],
            },
        )

        try:
            final_state = self._graph.invoke(initial_state, thread_id=str(run.id))
        except Exception as exc:
            logger.exception("Workflow resume failed: %s", exc)
            run.errors = [str(exc)]
            run.status = WorkflowStatus.FAILED
            run.touch()
            self._workflow_runs.update(run)
            raise WorkflowError(str(exc)) from exc

        refreshed = self._workflow_runs.get_by_id(run.id)
        if refreshed is None:
            raise WorkflowError(f"Workflow run {run.id} disappeared after resume")
        return self._ensure_success(self._to_result(refreshed, final_state))

    def get_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return self._workflow_runs.get_by_id(workflow_run_id)

    def _to_result(
        self,
        workflow_run: WorkflowRun,
        final_state: PresentationWorkflowState | dict[str, Any],
    ) -> WorkflowRunResult:
        restored = restore_domain_artifacts(workflow_run.state)
        if isinstance(final_state, dict):
            restored.update(restore_domain_artifacts(cast(dict[str, Any], final_state)))

        presentation = restored.get("presentation")
        if presentation is None:
            raise WorkflowError(
                f"Workflow run {workflow_run.id} is missing presentation in final state"
            )

        json_path_value = workflow_run.state.get("json_path") or final_state.get("json_path")
        spec_path_value = workflow_run.state.get("spec_path") or final_state.get("spec_path")
        editable_pptx_value = workflow_run.state.get("editable_pptx_path") or final_state.get(
            "editable_pptx_path"
        )
        marp_md_value = workflow_run.state.get("marp_md_path") or final_state.get("marp_md_path")
        marp_pptx_value = workflow_run.state.get("marp_pptx_path") or final_state.get(
            "marp_pptx_path"
        )
        pdf_value = workflow_run.state.get("pdf_path") or final_state.get("pdf_path")
        preview_values = workflow_run.state.get("preview_image_paths") or final_state.get(
            "preview_image_paths"
        ) or []
        warnings = list(
            workflow_run.state.get("render_warnings") or final_state.get("render_warnings") or []
        )

        render = RenderResult.from_state_paths(
            json_path=json_path_value,
            spec_path=spec_path_value,
            editable_pptx_path=editable_pptx_value,
            marp_md_path=marp_md_value,
            marp_pptx_path=marp_pptx_value,
            pdf_path=pdf_value,
            preview_images=[Path(str(item)) for item in preview_values],
            warnings=warnings,
        )

        return WorkflowRunResult(
            workflow_run=workflow_run,
            presentation=presentation,
            brief=restored.get("brief"),
            storyline=restored.get("storyline"),
            slides=list(restored.get("slides", [])),
            render=render,
            errors=list(workflow_run.errors),
        )

    @staticmethod
    def _ensure_success(result: WorkflowRunResult) -> WorkflowRunResult:
        if result.errors:
            message = "; ".join(result.errors)
            raise WorkflowError(f"Presentation workflow failed: {message}")
        return result
