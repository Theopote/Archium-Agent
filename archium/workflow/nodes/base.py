"""Shared workflow node infrastructure."""

from __future__ import annotations

from uuid import UUID

from archium.application.automated_review_service import AutomatedReviewService
from archium.application.review_service import slides_are_approved
from archium.application.workflow_checkpoint import commit_workflow_checkpoint, finalize_run_state
from archium.domain.enums import ApprovalStatus, WorkflowStatus
from archium.domain.review import ReviewIssue, merge_review_findings
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository
from archium.logging import ArchiumLogAdapter, get_logger
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.serialization import snapshot_state
from archium.workflow.state import PresentationWorkflowState


class WorkflowNodeBase:
    """Shared helpers for LangGraph presentation workflow nodes."""

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

    @staticmethod
    def _merge_review_findings(
        state: PresentationWorkflowState,
        new_issues: list[ReviewIssue],
        reviewer: AutomatedReviewService,
    ) -> dict[str, object]:
        return merge_review_findings(
            list(state.get("review_issues", [])),
            new_issues,
            reviewer.summarize_for_slides,
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
        finalize_run_state(run, snapshot_state(state))
        run.errors = list(state.get("errors", []))
        output_files = list(run.output_files)
        json_path = state.get("json_path")
        if json_path and json_path not in output_files:
            output_files.append(json_path)
        marp_md_path = state.get("marp_md_path")
        if marp_md_path and marp_md_path not in output_files:
            output_files.append(marp_md_path)
        marp_pptx_path = state.get("marp_pptx_path")
        if marp_pptx_path and marp_pptx_path not in output_files:
            output_files.append(marp_pptx_path)
        pdf_path = state.get("pdf_path")
        if pdf_path and pdf_path not in output_files:
            output_files.append(pdf_path)
        for preview_path in state.get("preview_image_paths", []):
            if preview_path and preview_path not in output_files:
                output_files.append(preview_path)
        run.output_files = output_files
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)
        commit_workflow_checkpoint(self._runtime.session, self._runtime.settings)

    def _load_slides_for_export(self, state: PresentationWorkflowState) -> list[SlideSpec]:
        presentation_id = UUID(state["presentation_id"])
        return self._presentations.list_slides(presentation_id)

    def _pending_human_review(self, state: PresentationWorkflowState) -> bool:
        if state.get("require_brief_review"):
            brief = state.get("brief")
            if brief is not None:
                refreshed = self._presentations.get_brief(brief.id)
                if refreshed is not None and refreshed.approval_status != ApprovalStatus.APPROVED:
                    return True

        if state.get("require_storyline_review"):
            storyline = state.get("storyline")
            if storyline is not None:
                refreshed_storyline = self._presentations.get_storyline(storyline.id)
                if (
                    refreshed_storyline is not None
                    and refreshed_storyline.approval_status != ApprovalStatus.APPROVED
                ):
                    return True

        if state.get("require_outline_review"):
            outline = state.get("outline")
            if outline is not None:
                refreshed_outline = self._presentations.get_outline(outline.id)
                if (
                    refreshed_outline is not None
                    and refreshed_outline.approval_status != ApprovalStatus.APPROVED
                ):
                    return True

        if state.get("require_slides_review"):
            slides = self._load_slides_for_export(state)
            if slides and not slides_are_approved(slides):
                return True

        return False
