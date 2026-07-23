"""Workflow nodes for PresentationManuscript (Research → Design boundary)."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.application.presentation_manuscript_service import PresentationManuscriptService
from archium.domain.enums import PresentationWorkflowStep
from archium.domain.presentation_manuscript import ManuscriptStatus
from archium.workflow.nodes.base import WorkflowNodeBase
from archium.workflow.state import PresentationWorkflowState


class ManuscriptNodesMixin(WorkflowNodeBase):
    """Build and gate PresentationManuscript before narrative/design agents."""

    def build_manuscript(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": PresentationWorkflowStep.BUILD_MANUSCRIPT.value}

        request = state.get("request")
        if request is None or not request.use_manuscript_pipeline:
            return {"current_step": PresentationWorkflowStep.BUILD_MANUSCRIPT.value}

        existing = state.get("manuscript")
        if existing is not None:
            refreshed = PresentationManuscriptService(self._runtime.session).get(existing.id)
            if refreshed is not None:
                return {
                    "manuscript": refreshed,
                    "current_step": PresentationWorkflowStep.BUILD_MANUSCRIPT.value,
                }

        try:
            project_id = UUID(state["project_id"])
            presentation_id = UUID(state["presentation_id"])
            service = PresentationManuscriptService(self._runtime.session)
            manuscript = service.build_from_project_research(
                project_id=project_id,
                presentation_id=presentation_id,
                title=request.title,
                project_summary=request.purpose or request.title,
                narrative_thesis=request.core_message or request.purpose or request.title,
            )
            if not state.get("require_manuscript_review"):
                manuscript.mark_ready()
                manuscript = service.save(manuscript)
            next_state: PresentationWorkflowState = {
                "manuscript": manuscript,
                "current_step": PresentationWorkflowStep.BUILD_MANUSCRIPT.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info(
                "Manuscript built for presentation %s (%d facts)",
                presentation_id,
                len(manuscript.verified_facts),
            )
            return next_state
        except Exception as exc:  # noqa: BLE001
            logger.exception("Manuscript build failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": PresentationWorkflowStep.BUILD_MANUSCRIPT.value,
            }

    def sync_manuscript_from_storyline(
        self, state: PresentationWorkflowState
    ) -> PresentationWorkflowState:
        """Optional post-storyline refresh — keeps outline_from_manuscript aligned."""
        logger = self._logger(state)
        request = state.get("request")
        manuscript = state.get("manuscript")
        storyline = state.get("storyline")
        if (
            request is None
            or not request.use_manuscript_pipeline
            or manuscript is None
            or storyline is None
        ):
            return {"current_step": PresentationWorkflowStep.STORYLINE.value}

        try:
            service = PresentationManuscriptService(self._runtime.session)
            updated = service.apply_storyline_sections(manuscript, storyline)
            next_state: PresentationWorkflowState = {
                "manuscript": updated,
                "current_step": PresentationWorkflowStep.STORYLINE.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Manuscript sections synced from storyline")
            return next_state
        except Exception as exc:  # noqa: BLE001
            logger.exception("Manuscript sync failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": PresentationWorkflowStep.STORYLINE.value,
            }

    @staticmethod
    def manuscript_ready(manuscript) -> bool:  # type: ignore[no-untyped-def]
        return manuscript is not None and manuscript.status == ManuscriptStatus.READY
