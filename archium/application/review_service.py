"""Human review and editing for Brief and Storyline artifacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.review_models import (
    BriefUpdate,
    ChapterUpdate,
    PresentationReviewContext,
    StorylineUpdate,
)
from archium.domain.enums import ApprovalStatus, WorkflowStatus
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    WorkflowRunRepository,
)


class PresentationReviewService:
    """Load, edit, and approve presentation planning artifacts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._workflow_runs = WorkflowRunRepository(session)

    def get_review_context(
        self,
        presentation_id: UUID,
        *,
        workflow_run_id: UUID | None = None,
    ) -> PresentationReviewContext | None:
        presentation = self._presentations.get_presentation(presentation_id)
        if presentation is None:
            return None

        brief = None
        if presentation.current_brief_id is not None:
            brief = self._presentations.get_brief(presentation.current_brief_id)
        if brief is None:
            briefs = self._presentations.list_briefs(presentation_id)
            brief = briefs[0] if briefs else None

        storyline = None
        if presentation.current_storyline_id is not None:
            storyline = self._presentations.get_storyline(presentation.current_storyline_id)
        if storyline is None:
            storylines = self._presentations.list_storylines(presentation_id)
            storyline = storylines[0] if storylines else None

        workflow_run = None
        if workflow_run_id is not None:
            workflow_run = self._workflow_runs.get_by_id(workflow_run_id)
        else:
            runs = self._workflow_runs.list_by_presentation(presentation_id)
            workflow_run = next(
                (run for run in runs if run.status == WorkflowStatus.AWAITING_REVIEW),
                runs[0] if runs else None,
            )

        return PresentationReviewContext(
            presentation=presentation,
            brief=brief,
            storyline=storyline,
            workflow_run=workflow_run,
        )

    def update_brief(self, brief_id: UUID, update: BriefUpdate) -> PresentationBrief:
        brief = self._require_brief(brief_id)
        brief.title = update.title.strip()
        brief.audience = update.audience.strip()
        brief.purpose = update.purpose.strip()
        brief.core_message = update.core_message.strip()
        brief.duration_minutes = update.duration_minutes
        brief.target_slide_count = update.target_slide_count
        brief.tone = update.tone.strip() or "professional"
        brief.language = update.language.strip() or "zh-CN"
        brief.required_sections = list(update.required_sections)
        brief.decisions_required = list(update.decisions_required)
        brief.audience_concerns = list(update.audience_concerns)
        brief.excluded_topics = list(update.excluded_topics)
        brief.approval_status = ApprovalStatus.DRAFT
        brief.touch()
        return self._presentations.save_brief(brief)

    def approve_brief(self, brief_id: UUID) -> PresentationBrief:
        brief = self._require_brief(brief_id)
        brief.approve()
        return self._presentations.save_brief(brief)

    def reject_brief(self, brief_id: UUID) -> PresentationBrief:
        brief = self._require_brief(brief_id)
        brief.reject()
        return self._presentations.save_brief(brief)

    def update_storyline(self, storyline_id: UUID, update: StorylineUpdate) -> Storyline:
        storyline = self._require_storyline(storyline_id)
        storyline.thesis = update.thesis.strip()
        storyline.narrative_pattern = update.narrative_pattern.strip() or "problem_solution"
        storyline.chapters = [_chapter_from_update(item) for item in update.chapters]
        storyline.approval_status = ApprovalStatus.DRAFT
        storyline.touch()
        return self._presentations.save_storyline(storyline)

    def approve_storyline(self, storyline_id: UUID) -> Storyline:
        storyline = self._require_storyline(storyline_id)
        storyline.approve()
        return self._presentations.save_storyline(storyline)

    def reject_storyline(self, storyline_id: UUID) -> Storyline:
        storyline = self._require_storyline(storyline_id)
        storyline.reject()
        return self._presentations.save_storyline(storyline)

    def ensure_can_continue(self, workflow_run_id: UUID) -> PresentationReviewContext:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(f"Workflow run {workflow_run_id} is not awaiting review")

        context = self.get_review_context(run.presentation_id, workflow_run_id=run.id)
        if context is None:
            raise WorkflowError(f"Presentation {run.presentation_id} not found")

        gate = run.state.get("review_gate")
        if gate == "brief":
            if context.brief is None:
                raise WorkflowError("Brief is missing for review continuation")
            if context.brief.approval_status != ApprovalStatus.APPROVED:
                raise WorkflowError("Brief must be approved before continuing")
        elif gate == "storyline":
            if context.storyline is None:
                raise WorkflowError("Storyline is missing for review continuation")
            if context.storyline.approval_status != ApprovalStatus.APPROVED:
                raise WorkflowError("Storyline must be approved before continuing")
        else:
            raise WorkflowError(f"Unknown review gate: {gate}")

        return context

    def _require_brief(self, brief_id: UUID) -> PresentationBrief:
        brief = self._presentations.get_brief(brief_id)
        if brief is None:
            raise WorkflowError(f"Brief {brief_id} not found")
        return brief

    def _require_storyline(self, storyline_id: UUID) -> Storyline:
        storyline = self._presentations.get_storyline(storyline_id)
        if storyline is None:
            raise WorkflowError(f"Storyline {storyline_id} not found")
        return storyline


def _chapter_from_update(update: ChapterUpdate) -> Chapter:
    return Chapter(
        id=update.id.strip(),
        title=update.title.strip(),
        purpose=update.purpose.strip(),
        key_message=update.key_message.strip(),
        order=update.order,
        estimated_slide_count=update.estimated_slide_count,
    )
