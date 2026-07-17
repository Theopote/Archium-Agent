"""Regenerate Brief, Storyline, or SlideSpec after rejection or revision."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.presentation_models import PresentationRequest
from archium.application.presentation_service import PresentationService
from archium.application.review_service import PresentationReviewService
from archium.application.slide_history_service import SlideHistoryService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import ApprovalStatus, WorkflowStatus, WorkflowStep
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.domain.workflow import WorkflowRun
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.workflow.serialization import request_from_dict, snapshot_state


class RegenerationService:
    """Re-run individual pipeline stages for a presentation."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._workflow_runs = WorkflowRunRepository(session)
        self._pipeline = PresentationService(session, llm, settings=self._settings)
        self._review = PresentationReviewService(session)
        self._history = SlideHistoryService(session)

    def regenerate_brief(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None = None,
    ) -> PresentationBrief:
        presentation = self._require_presentation(presentation_id)
        request = self._load_request(presentation_id, workflow_run_id=workflow_run_id)
        brief = self._pipeline.generate_brief(presentation.project_id, presentation_id, request)
        brief.approval_status = ApprovalStatus.PENDING
        brief = self._presentations.save_brief(brief)

        presentation.current_brief_id = brief.id
        presentation.current_storyline_id = None
        self._presentations.update_presentation(presentation)
        self._archive_and_delete_slides(presentation_id)
        self._pause_for_review(
            presentation_id,
            workflow_run_id=workflow_run_id,
            gate="brief",
            step=WorkflowStep.REVIEW_BRIEF,
            brief=brief,
            storyline=None,
            slides=[],
        )
        return brief

    def regenerate_storyline(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None = None,
    ) -> Storyline:
        context = self._review.get_review_context(presentation_id, workflow_run_id=workflow_run_id)
        if context is None or context.brief is None:
            raise WorkflowError("Cannot regenerate storyline without an approved brief context")
        if context.brief.approval_status != ApprovalStatus.APPROVED:
            raise WorkflowError("Brief must be approved before regenerating storyline")

        storyline = self._pipeline.generate_storyline(context.presentation.project_id, context.brief)
        storyline.approval_status = ApprovalStatus.PENDING
        storyline = self._presentations.save_storyline(storyline)

        presentation = context.presentation
        presentation.current_storyline_id = storyline.id
        self._presentations.update_presentation(presentation)
        self._archive_and_delete_slides(presentation_id)
        self._pause_for_review(
            presentation_id,
            workflow_run_id=workflow_run_id,
            gate="storyline",
            step=WorkflowStep.REVIEW_STORYLINE,
            brief=context.brief,
            storyline=storyline,
            slides=[],
        )
        return storyline

    def regenerate_slide_plan(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None = None,
        require_review: bool = True,
    ) -> list[SlideSpec]:
        context = self._review.get_review_context(presentation_id, workflow_run_id=workflow_run_id)
        if context is None or context.brief is None or context.storyline is None:
            raise WorkflowError("Cannot regenerate slides without brief and storyline")
        if context.brief.approval_status != ApprovalStatus.APPROVED:
            raise WorkflowError("Brief must be approved before regenerating slides")
        if context.storyline.approval_status != ApprovalStatus.APPROVED:
            raise WorkflowError("Storyline must be approved before regenerating slides")

        self._archive_and_delete_slides(presentation_id, slides=context.slides)
        slides = self._pipeline.generate_slide_plan(
            context.presentation.project_id,
            context.brief,
            context.storyline,
        )
        saved: list[SlideSpec] = []
        for slide in slides:
            if require_review:
                slide.mark_planned()
            else:
                slide.approve()
            saved.append(self._presentations.save_slide(slide))

        self._pause_for_review(
            presentation_id,
            workflow_run_id=workflow_run_id,
            gate="slides",
            step=WorkflowStep.REVIEW_SLIDES,
            brief=context.brief,
            storyline=context.storyline,
            slides=saved,
        )
        return saved

    def _load_request(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None,
    ) -> PresentationRequest:
        run = self._resolve_workflow_run(presentation_id, workflow_run_id)
        if run is not None and "request" in run.state:
            return request_from_dict(run.state["request"])
        context = self._review.get_review_context(presentation_id, workflow_run_id=workflow_run_id)
        if context is None or context.brief is None:
            raise WorkflowError("Cannot resolve PresentationRequest for regeneration")
        brief = context.brief
        return PresentationRequest(
            title=brief.title,
            audience=brief.audience,
            purpose=brief.purpose,
            core_message=brief.core_message,
            duration_minutes=brief.duration_minutes,
            target_slide_count=brief.target_slide_count,
            required_sections=list(brief.required_sections),
            tone=brief.tone,
            language=brief.language,
        )

    def _pause_for_review(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None,
        gate: str,
        step: WorkflowStep,
        brief: PresentationBrief | None,
        storyline: Storyline | None,
        slides: list[SlideSpec],
    ) -> None:
        run = self._resolve_workflow_run(presentation_id, workflow_run_id)
        if run is None:
            return

        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            return

        restored = {
            "project_id": str(run.project_id),
            "presentation_id": str(presentation_id),
            "workflow_run_id": str(run.id),
            "presentation": presentation,
            "brief": brief,
            "storyline": storyline,
            "slides": slides,
            "current_step": step.value,
            "review_gate": gate,
            "export_json": run.state.get("export_json", True),
            "export_marp": run.state.get("export_marp", False),
            "export_pptx": run.state.get("export_pptx", False),
            "require_brief_review": run.state.get("require_brief_review", False),
            "require_storyline_review": run.state.get("require_storyline_review", False),
            "require_slides_review": run.state.get("require_slides_review", False),
            "errors": [],
        }
        if "request" in run.state:
            restored["request"] = request_from_dict(run.state["request"])

        run.status = WorkflowStatus.AWAITING_REVIEW
        run.state = snapshot_state(restored)  # type: ignore[arg-type]
        run.errors = []
        run.touch()
        self._workflow_runs.update(run)

    def _archive_and_delete_slides(
        self,
        presentation_id: UUID,
        *,
        slides: list[SlideSpec] | None = None,
    ) -> None:
        existing = slides if slides is not None else self._presentations.list_slides(presentation_id)
        if existing:
            self._history.archive_slides_before_regeneration(existing)
        self._presentations.delete_slides_for_presentation(presentation_id)

    def _resolve_workflow_run(
        self,
        presentation_id: UUID,
        workflow_run_id: UUID | None,
    ) -> WorkflowRun | None:
        if workflow_run_id is not None:
            return self._workflow_runs.get_by_id(workflow_run_id)
        runs = self._workflow_runs.list_by_presentation(presentation_id)
        if not runs:
            return None
        return next(
            (run for run in runs if run.status == WorkflowStatus.AWAITING_REVIEW),
            runs[0],
        )

    def _require_presentation(self, presentation_id: UUID) -> Presentation:
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            raise WorkflowError(f"Presentation {presentation_id} not found")
        return presentation
