"""LangGraph node implementations for the presentation workflow."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.domain.enums import PresentationStatus, WorkflowStatus, WorkflowStep
from archium.infrastructure.database.repositories import PresentationRepository
from archium.logging import ArchiumLogAdapter, get_logger
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.serialization import snapshot_state
from archium.workflow.state import PresentationWorkflowState


class PresentationWorkflowNodes:
    """Node handlers that delegate to the Stage 6 presentation pipeline."""

    def __init__(self, runtime: PresentationWorkflowRuntime) -> None:
        self._runtime = runtime
        self._presentations = PresentationRepository(runtime.session)

    def _logger(self, state: PresentationWorkflowState) -> ArchiumLogAdapter:
        workflow_run_id = state.get("workflow_run_id", "-")
        return get_logger(
            __name__,
            operation="presentation_workflow",
            workflow_run_id=workflow_run_id,
        )

    def _persist_checkpoint(
        self,
        state: PresentationWorkflowState,
        *,
        status: WorkflowStatus | None = None,
    ) -> None:
        workflow_run_id = state.get("workflow_run_id")
        if workflow_run_id is None:
            return
        run = self._runtime.workflow_runs.get_by_id(UUID(workflow_run_id))
        if run is None:
            return
        run.state = snapshot_state(state)
        run.errors = list(state.get("errors", []))
        output_files = list(run.output_files)
        json_path = state.get("json_path")
        if json_path and json_path not in output_files:
            output_files.append(json_path)
        run.output_files = output_files
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)

    def generate_brief(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.BRIEF.value}

        try:
            project_id = UUID(state["project_id"])
            presentation_id = UUID(state["presentation_id"])
            request = state["request"]
            brief = self._runtime.presentation_service.generate_brief(
                project_id,
                presentation_id,
                request,
            )
            next_state: PresentationWorkflowState = {
                "brief": brief,
                "current_step": WorkflowStep.BRIEF.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Brief generated for presentation %s", presentation_id)
            return next_state
        except Exception as exc:
            logger.exception("Brief generation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.BRIEF.value,
            }

    def generate_storyline(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.STORYLINE.value}

        brief = state.get("brief")
        if brief is None:
            return {
                "errors": ["Cannot generate storyline without brief"],
                "current_step": WorkflowStep.STORYLINE.value,
            }

        try:
            project_id = UUID(state["project_id"])
            storyline = self._runtime.presentation_service.generate_storyline(project_id, brief)
            next_state: PresentationWorkflowState = {
                "storyline": storyline,
                "current_step": WorkflowStep.STORYLINE.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Storyline generated for presentation %s", state["presentation_id"])
            return next_state
        except Exception as exc:
            logger.exception("Storyline generation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.STORYLINE.value,
            }

    def generate_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.SLIDES.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot generate slides without brief and storyline"],
                "current_step": WorkflowStep.SLIDES.value,
            }

        try:
            project_id = UUID(state["project_id"])
            slides = self._runtime.presentation_service.generate_slide_plan(
                project_id,
                brief,
                storyline,
            )
            next_state: PresentationWorkflowState = {
                "slides": slides,
                "current_step": WorkflowStep.SLIDES.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info(
                "Slide plan generated for presentation %s (%d slides)",
                state["presentation_id"],
                len(slides),
            )
            return next_state
        except Exception as exc:
            logger.exception("Slide planning failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.SLIDES.value,
            }

    def export_json(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EXPORT.value}
        if not state.get("export_json", True):
            return {"current_step": WorkflowStep.EXPORT.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = state.get("slides", [])
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export JSON without brief and storyline"],
                "current_step": WorkflowStep.EXPORT.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            json_path = self._runtime.renderer.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "json_path": str(json_path),
                "current_step": WorkflowStep.EXPORT.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported presentation JSON to %s", json_path)
            return next_state
        except Exception as exc:
            logger.exception("JSON export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.EXPORT.value,
            }

    def finalize(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        presentation = state.get("presentation")
        brief = state.get("brief")
        storyline = state.get("storyline")
        errors = list(state.get("errors", []))

        if presentation is not None and not errors:
            presentation.status = PresentationStatus.REVIEW
            presentation.current_brief_id = brief.id if brief else None
            presentation.current_storyline_id = storyline.id if storyline else None
            presentation = self._presentations.update_presentation(presentation)
            status = WorkflowStatus.COMPLETED
            step = WorkflowStep.FINALIZE.value
        else:
            status = WorkflowStatus.FAILED
            step = WorkflowStep.FAILED.value

        next_state: PresentationWorkflowState = {
            "presentation": presentation,
            "current_step": step,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged, status=status)
        if errors:
            logger.error("Workflow failed with %d error(s)", len(errors))
        else:
            logger.info("Workflow completed for presentation %s", state.get("presentation_id"))
        return next_state
