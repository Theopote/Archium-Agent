"""Export workflow nodes — JSON, PresentationSpec, Marp, finalize."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.application.render_export import export_marp_extras, export_pptxgen_extras
from archium.domain.enums import PresentationStatus, WorkflowStatus, WorkflowStep
from archium.workflow.nodes.base import WorkflowNodeBase
from archium.workflow.state import PresentationWorkflowState


class ExportNodesMixin(WorkflowNodeBase):
    """Export presentation artifacts and finalize workflow status."""

    def export_json(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EXPORT.value}
        if not state.get("export_json", True):
            return {"current_step": WorkflowStep.EXPORT.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export JSON without brief and storyline"],
                "current_step": WorkflowStep.EXPORT.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            json_path = self._runtime.json_renderer.render(
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

    def export_presentation_spec(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.PRESENTATION_SPEC.value}
        if not state.get("export_presentation_spec", False):
            return {"current_step": WorkflowStep.PRESENTATION_SPEC.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export PresentationSpec without brief and storyline"],
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            project_id = UUID(state["project_id"])
            spec_path = self._runtime.pptxgen_renderer.render(
                presentation_id=presentation_id,
                project_id=project_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "spec_path": str(spec_path),
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }
            if state.get("export_editable_pptx", False):
                extras = export_pptxgen_extras(
                    self._runtime.pptxgen_renderer,
                    spec_path,
                    export_editable_pptx=True,
                )
                if extras.editable_pptx_path is not None:
                    next_state["editable_pptx_path"] = str(extras.editable_pptx_path)
                if extras.warnings:
                    next_state["render_warnings"] = extras.warnings

            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported PresentationSpec to %s", spec_path)
            return next_state
        except Exception as exc:
            logger.exception("PresentationSpec export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }

    def export_marp(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.MARP.value}
        if not state.get("export_marp", False):
            return {"current_step": WorkflowStep.MARP.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export Marp without brief and storyline"],
                "current_step": WorkflowStep.MARP.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            marp_md_path = self._runtime.marp_renderer.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "marp_md_path": str(marp_md_path),
                "current_step": WorkflowStep.MARP.value,
            }
            export_pptx = bool(state.get("export_pptx", False))
            export_pdf = bool(state.get("export_pdf", False))
            export_preview_images = bool(state.get("export_preview_images", False))
            if export_pptx or export_pdf or export_preview_images:
                extras = export_marp_extras(
                    self._runtime.marp_renderer,
                    marp_md_path,
                    export_pptx=export_pptx,
                    export_pdf=export_pdf,
                    export_preview_images=export_preview_images,
                )
                if extras.pptx_path is not None:
                    next_state["marp_pptx_path"] = str(extras.pptx_path)
                if extras.pdf_path is not None:
                    next_state["pdf_path"] = str(extras.pdf_path)
                if extras.preview_images:
                    next_state["preview_image_paths"] = [
                        str(path) for path in extras.preview_images
                    ]
                if extras.warnings:
                    next_state["render_warnings"] = extras.warnings

            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported Marp presentation to %s", marp_md_path)
            return next_state
        except Exception as exc:
            logger.exception("Marp export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.MARP.value,
            }

    def finalize(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        presentation = state.get("presentation")
        brief = state.get("brief")
        storyline = state.get("storyline")
        errors = list(state.get("errors", []))

        if presentation is not None and not errors:
            presentation.current_brief_id = brief.id if brief else None
            presentation.current_storyline_id = storyline.id if storyline else None
            awaiting_review = self._pending_human_review(state)
            has_exports = bool(state.get("json_path") or state.get("marp_md_path"))

            if awaiting_review:
                presentation.status = PresentationStatus.IN_PROGRESS
                status = WorkflowStatus.AWAITING_REVIEW
                step = WorkflowStep.FINALIZE.value
            elif has_exports:
                presentation.status = PresentationStatus.EXPORTED
                status = WorkflowStatus.COMPLETED
                step = WorkflowStep.FINALIZE.value
            else:
                presentation.status = PresentationStatus.REVIEW
                status = WorkflowStatus.COMPLETED
                step = WorkflowStep.FINALIZE.value

            presentation = self._presentations.update_presentation(presentation)
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
