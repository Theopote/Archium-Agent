"""Review workflow nodes — four-layer QA, repair, human review gates."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from langgraph.types import interrupt

from archium.application.automated_review_service import (
    AutomatedReviewService,
    critical_export_block_messages,
)
from archium.application.presentation_manuscript_service import PresentationManuscriptService
from archium.application.review_service import slides_are_approved
from archium.application.slide_repair_service import SlideRepairService, split_affected_slide_ids
from archium.domain.enums import ApprovalStatus, WorkflowStatus, WorkflowStep
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import ManuscriptStatus, PresentationManuscript
from archium.workflow.nodes.base import WorkflowNodeBase
from archium.workflow.state import PresentationWorkflowState


class ReviewNodesMixin(WorkflowNodeBase):
    """Automated four-layer review, slide repair, and human review pauses."""

    def run_content_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.CONTENT_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.CONTENT_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            content_issues = reviewer.run_content_review(
                presentation_id,
                slides,
                brief=state.get("brief"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, content_issues, reviewer),
                    "current_step": WorkflowStep.CONTENT_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Content review recorded %d issue(s)", len(content_issues))
            return next_state
        except Exception as exc:
            logger.exception("Content review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.CONTENT_REVIEW.value,
            }

    def run_evidence_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EVIDENCE_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.EVIDENCE_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            evidence_issues = reviewer.run_evidence_review(
                presentation_id,
                slides,
                context_bundle=state.get("context_bundle"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, evidence_issues, reviewer),
                    "current_step": WorkflowStep.EVIDENCE_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Evidence review recorded %d issue(s)", len(evidence_issues))
            return next_state
        except Exception as exc:
            logger.exception("Evidence review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.EVIDENCE_REVIEW.value,
            }

    def run_architectural_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            architectural_issues = reviewer.run_architectural_review(
                presentation_id,
                slides,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, architectural_issues, reviewer),
                    "current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Architectural review recorded %d issue(s)", len(architectural_issues))
            return next_state
        except Exception as exc:
            logger.exception("Architectural review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value,
            }

    def run_layout_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.LAYOUT_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.LAYOUT_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            project_id = UUID(state["project_id"]) if state.get("project_id") else None
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            layout_issues = reviewer.run_layout_review(
                presentation_id,
                slides,
                project_id=project_id,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
                context_bundle=state.get("context_bundle"),
                renovation_issue_map=state.get("renovation_issue_map"),
                reference_style_profile=state.get("reference_style_profile"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, layout_issues, reviewer),
                    "current_step": WorkflowStep.LAYOUT_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Layout review recorded %d issue(s)", len(layout_issues))
            return next_state
        except Exception as exc:
            logger.exception("Layout review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.LAYOUT_REVIEW.value,
            }

    def run_professional_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        """Backward-compatible alias: runs architectural review only."""
        return self.run_architectural_review(state)

    def repair_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.REPAIR_SLIDES.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.REPAIR_SLIDES.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            repairer = SlideRepairService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            repaired_slides, repair_count, repair_records = repairer.repair_slides(
                presentation_id,
                slides,
                list(state.get("review_issues", [])),
                brief=state.get("brief"),
                storyline=state.get("storyline"),
                outline=state.get("outline"),
                manuscript=state.get("manuscript"),
                project_id=UUID(state["project_id"]),
            )
            split_slide_ids = split_affected_slide_ids(repair_records)
            matched_asset_count = state.get("matched_asset_count", 0)
            if split_slide_ids:
                matched_asset_count = sum(
                    1
                    for slide in repaired_slides
                    for requirement in slide.visual_requirements
                    if requirement.preferred_asset_ids
                )
            prior_records = list(state.get("slide_repair_records", []))
            next_state: PresentationWorkflowState = {
                "slides": repaired_slides,
                "repaired_slide_count": repair_count,
                "repair_round": state.get("repair_round", 0) + 1,
                "slide_repair_records": [*prior_records, *repair_records],
                "matched_asset_count": matched_asset_count,
                "review_issues": [],
                "slide_review_issues": [],
                "current_step": WorkflowStep.REPAIR_SLIDES.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Slide repair updated %d slide(s)", repair_count)
            return next_state
        except Exception as exc:
            logger.exception("Slide repair failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.REPAIR_SLIDES.value,
            }

    def review_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        """Summarize automated review findings before export or human review."""
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.SLIDE_VALIDATION.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {
                "errors": ["Cannot review slides without a slide plan"],
                "current_step": WorkflowStep.SLIDE_VALIDATION.value,
            }

        review_issues = list(state.get("review_issues", []))
        slide_review_issues = list(state.get("slide_review_issues", []))
        if not slide_review_issues and review_issues:
            slide_review_issues = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            ).summarize_for_slides(review_issues)

        block_errors = critical_export_block_messages(
            review_issues,
            block_enabled=self._runtime.settings.block_export_on_critical_review,
        )
        if block_errors:
            logger.error("Export blocked by %d critical review issue(s)", len(block_errors))
            return {
                "errors": block_errors,
                "slide_review_issues": slide_review_issues,
                "current_step": WorkflowStep.SLIDE_VALIDATION.value,
            }

        next_state: PresentationWorkflowState = {
            "slide_review_issues": slide_review_issues,
            "current_step": WorkflowStep.SLIDE_VALIDATION.value,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged)
        if slide_review_issues:
            logger.warning("Slide validation summary: %d issue(s)", len(slide_review_issues))
        else:
            logger.info("Slide validation passed for %d slides", len(slides))
        return next_state

    @staticmethod
    def _coerce_domain(model_cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, model_cls):
            return value
        if isinstance(value, dict):
            return model_cls.model_validate(value)
        return value

    @staticmethod
    def _coerce_manuscript(manuscript):  # type: ignore[no-untyped-def]
        if manuscript is None or isinstance(manuscript, PresentationManuscript):
            return manuscript
        return PresentationManuscript.model_validate(manuscript)

    def _refresh_review_artifacts(
        self,
        state: PresentationWorkflowState,
        gate: str,
    ) -> PresentationWorkflowState:
        presentation_id = UUID(state["presentation_id"])
        updates: PresentationWorkflowState = {}

        brief = self._coerce_domain(PresentationBrief, state.get("brief"))
        if brief is not None:
            refreshed_brief = self._presentations.get_brief(brief.id)
            if refreshed_brief is not None:
                updates["brief"] = refreshed_brief

        if gate == "manuscript":
            manuscript = self._coerce_manuscript(state.get("manuscript"))
            if manuscript is not None:
                refreshed_manuscript = PresentationManuscriptService(
                    self._runtime.session
                ).get(manuscript.id)
                if refreshed_manuscript is not None:
                    updates["manuscript"] = refreshed_manuscript

        if gate in {"storyline", "outline", "slides"}:
            storyline = self._coerce_domain(Storyline, state.get("storyline"))
            if storyline is not None:
                refreshed_storyline = self._presentations.get_storyline(storyline.id)
                if refreshed_storyline is not None:
                    updates["storyline"] = refreshed_storyline

        if gate in {"outline", "slides"}:
            outline = self._coerce_domain(OutlinePlan, state.get("outline"))
            if outline is not None:
                refreshed_outline = self._presentations.get_outline(outline.id)
                if refreshed_outline is not None:
                    updates["outline"] = refreshed_outline

        if gate == "slides":
            updates["slides"] = self._presentations.list_slides(presentation_id)

        return updates

    def _gate_ready_to_continue(self, state: PresentationWorkflowState, gate: str) -> bool:
        if gate == "manuscript":
            manuscript = self._coerce_manuscript(state.get("manuscript"))
            if manuscript is None:
                return False
            refreshed_manuscript = PresentationManuscriptService(
                self._runtime.session
            ).get(manuscript.id)
            return (
                refreshed_manuscript is not None
                and refreshed_manuscript.status == ManuscriptStatus.READY
            )
        if gate == "brief":
            brief = self._coerce_domain(PresentationBrief, state.get("brief"))
            if brief is None:
                return False
            refreshed_brief = self._presentations.get_brief(brief.id)
            return (
                refreshed_brief is not None
                and refreshed_brief.approval_status == ApprovalStatus.APPROVED
            )
        if gate == "storyline":
            storyline = self._coerce_domain(Storyline, state.get("storyline"))
            if storyline is None:
                return False
            refreshed_storyline = self._presentations.get_storyline(storyline.id)
            return (
                refreshed_storyline is not None
                and refreshed_storyline.approval_status == ApprovalStatus.APPROVED
            )
        if gate == "outline":
            outline = self._coerce_domain(OutlinePlan, state.get("outline"))
            if outline is None:
                return False
            refreshed_outline = self._presentations.get_outline(outline.id)
            return (
                refreshed_outline is not None
                and refreshed_outline.approval_status == ApprovalStatus.APPROVED
            )
        if gate == "slides":
            slides = self._presentations.list_slides(UUID(state["presentation_id"]))
            return bool(slides) and slides_are_approved(slides)
        return False

    def pause_for_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        review_steps = {
            WorkflowStep.REVIEW_MANUSCRIPT.value,
            WorkflowStep.REVIEW_BRIEF.value,
            WorkflowStep.REVIEW_STORYLINE.value,
            WorkflowStep.REVIEW_OUTLINE.value,
            WorkflowStep.REVIEW_SLIDES.value,
        }

        workflow_run_id = state.get("workflow_run_id")
        if workflow_run_id is not None:
            run = self._runtime.workflow_runs.get_by_id(UUID(workflow_run_id))
            if run is not None:
                existing_gate = run.state.get("review_gate")
                existing_step = run.state.get("current_step")
                if (
                    isinstance(existing_gate, str)
                    and existing_gate in {"manuscript", "brief", "storyline", "outline", "slides"}
                    and isinstance(existing_step, str)
                    and existing_step in review_steps
                    and self._gate_ready_to_continue(state, existing_gate)
                ):
                    refreshed = self._refresh_review_artifacts(state, existing_gate)
                    resume_state: PresentationWorkflowState = {
                        "review_gate": existing_gate,
                        "current_step": existing_step,
                        **refreshed,
                    }
                    resume_merged = cast(PresentationWorkflowState, {**state, **resume_state})
                    self._persist_checkpoint(resume_merged, status=WorkflowStatus.RUNNING)
                    logger.info("Workflow resumed after %s review", existing_gate)
                    return resume_state

        brief = state.get("brief")
        storyline = state.get("storyline")
        outline = state.get("outline")
        slides = self._load_slides_for_export(state)

        request = state.get("request")
        manuscript = self._coerce_manuscript(state.get("manuscript"))

        if (
            request is not None
            and request.use_manuscript_pipeline
            and state.get("require_manuscript_review")
            and manuscript is not None
            and manuscript.status != ManuscriptStatus.READY
        ):
            gate = "manuscript"
            step = WorkflowStep.REVIEW_MANUSCRIPT.value
        elif brief is not None and brief.approval_status != ApprovalStatus.APPROVED:
            gate = "brief"
            step = WorkflowStep.REVIEW_BRIEF.value
        elif storyline is not None and storyline.approval_status != ApprovalStatus.APPROVED:
            gate = "storyline"
            step = WorkflowStep.REVIEW_STORYLINE.value
        elif state.get("require_outline_review") and outline is not None and outline.approval_status != ApprovalStatus.APPROVED:
            gate = "outline"
            step = WorkflowStep.REVIEW_OUTLINE.value
        elif slides and state.get("require_slides_review") and not slides_are_approved(slides):
            gate = "slides"
            step = WorkflowStep.REVIEW_SLIDES.value
        else:
            return {"current_step": WorkflowStep.FINALIZE.value}

        next_state: PresentationWorkflowState = {
            "current_step": step,
            "review_gate": gate,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Workflow paused for %s review on presentation %s", gate, state.get("presentation_id"))

        interrupt({"gate": gate, "step": step})

        refreshed = self._refresh_review_artifacts(merged, gate)
        resume_state = {
            **next_state,
            **refreshed,
        }
        resume_merged = cast(PresentationWorkflowState, {**merged, **resume_state})
        self._persist_checkpoint(resume_merged, status=WorkflowStatus.RUNNING)
        logger.info("Workflow resumed after %s review", gate)
        return resume_state
