"""Human review and editing for Brief, Storyline, and SlideSpec artifacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_history_service import (
    BriefHistoryService,
    OutlineHistoryService,
    StorylineHistoryService,
)
from archium.application.presentation_manuscript_service import PresentationManuscriptService
from archium.application.review_models import (
    BriefUpdate,
    ChapterUpdate,
    OutlineSectionUpdate,
    OutlineUpdate,
    PresentationReviewContext,
    SlideUpdate,
    StorylineUpdate,
)
from archium.application.slide_history_service import SlideHistoryService
from archium.domain.enums import (
    ApprovalStatus,
    OutlineAudienceMode,
    RevisionSource,
    SlideStatus,
    SlideType,
    WorkflowStatus,
)
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.presentation_manuscript import ManuscriptStatus
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ReviewRepository,
    WorkflowRunRepository,
)


def slides_are_approved(slides: list[SlideSpec]) -> bool:
    if not slides:
        return False
    return all(slide.status == SlideStatus.APPROVED for slide in slides)


class PresentationReviewService:
    """Load, edit, and approve presentation planning artifacts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._workflow_runs = WorkflowRunRepository(session)
        self._reviews = ReviewRepository(session)
        self._history = SlideHistoryService(session)
        self._brief_history = BriefHistoryService(session)
        self._storyline_history = StorylineHistoryService(session)
        self._outline_history = OutlineHistoryService(session)

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

        slides = self._presentations.list_slides(presentation_id)

        outline = None
        if presentation.current_outline_id is not None:
            outline = self._presentations.get_outline(presentation.current_outline_id)
        if outline is None:
            outlines = self._presentations.list_outlines(presentation_id)
            outline = outlines[0] if outlines else None

        review_issues = self._reviews.list_by_presentation(presentation_id)

        workflow_run = None
        manuscript = None
        if workflow_run_id is not None:
            workflow_run = self._workflow_runs.get_by_id(workflow_run_id)
        else:
            runs = self._workflow_runs.list_by_presentation(presentation_id)
            workflow_run = next(
                (run for run in runs if run.status == WorkflowStatus.AWAITING_REVIEW),
                runs[0] if runs else None,
            )

        if workflow_run is not None:
            from archium.workflow.serialization import restore_domain_artifacts

            restored = restore_domain_artifacts(workflow_run.state)
            candidate = restored.get("manuscript")
            if candidate is not None:
                manuscript = PresentationManuscriptService(self._session).get(candidate.id)
        if manuscript is None:
            manuscripts = PresentationManuscriptService(self._session).list_for_project(
                presentation.project_id
            )
            manuscript = next(
                (item for item in manuscripts if item.presentation_id == presentation_id),
                None,
            )

        return PresentationReviewContext(
            presentation=presentation,
            brief=brief,
            storyline=storyline,
            outline=outline,
            manuscript=manuscript,
            slides=slides,
            review_issues=review_issues,
            workflow_run=workflow_run,
        )

    def list_review_issues(self, presentation_id: UUID) -> list[ReviewIssue]:
        return self._reviews.list_by_presentation(presentation_id)

    def list_review_issues_by_project(self, project_id: UUID) -> list[ReviewIssue]:
        return self._reviews.list_by_project(project_id)

    def resolve_review_issue(self, issue_id: UUID) -> ReviewIssue:
        issue = self._require_review_issue(issue_id)
        issue.resolve()
        return self._reviews.update(issue)

    def dismiss_review_issue(self, issue_id: UUID) -> ReviewIssue:
        issue = self._require_review_issue(issue_id)
        issue.dismiss()
        return self._reviews.update(issue)

    def list_slides(self, presentation_id: UUID) -> list[SlideSpec]:
        return self._presentations.list_slides(presentation_id)

    def get_slide(self, slide_id: UUID) -> SlideSpec | None:
        return self._presentations.get_slide(slide_id)

    def update_brief(self, brief_id: UUID, update: BriefUpdate) -> PresentationBrief:
        brief = self._require_brief(brief_id)
        self._brief_history.record_snapshot(brief, RevisionSource.MANUAL_EDIT)
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
        self._storyline_history.record_snapshot(storyline, RevisionSource.MANUAL_EDIT)
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

    def update_outline(self, outline_id: UUID, update: OutlineUpdate) -> OutlinePlan:
        outline = self._require_outline(outline_id)
        self._outline_history.record_snapshot(outline, RevisionSource.MANUAL_EDIT)
        try:
            audience_mode = OutlineAudienceMode(update.audience_mode)
        except ValueError:
            audience_mode = OutlineAudienceMode.GOVERNMENT
        outline.title = update.title.strip()
        outline.thesis = update.thesis.strip()
        outline.audience = update.audience.strip()
        outline.purpose = update.purpose.strip()
        outline.target_slide_count = update.target_slide_count
        outline.audience_mode = audience_mode
        outline.sections = [_outline_section_from_update(item) for item in update.sections]
        outline.approval_status = ApprovalStatus.DRAFT
        outline.touch()
        return self._presentations.save_outline(outline)

    def approve_outline(self, outline_id: UUID) -> OutlinePlan:
        outline = self._require_outline(outline_id)
        outline.approve()
        return self._presentations.save_outline(outline)

    def reject_outline(self, outline_id: UUID) -> OutlinePlan:
        outline = self._require_outline(outline_id)
        outline.reject()
        return self._presentations.save_outline(outline)

    def update_slide(self, slide_id: UUID, update: SlideUpdate) -> SlideSpec:
        slide = self._require_slide(slide_id)
        self._history.record_snapshot(slide, RevisionSource.MANUAL_EDIT)
        slide.chapter_id = update.chapter_id.strip()
        slide.order = update.order
        slide.title = update.title.strip()
        slide.message = update.message.strip()
        slide.slide_type = _parse_slide_type(update.slide_type)
        slide.layout_id = update.layout_id.strip() or "default"
        slide.key_points = list(update.key_points)
        slide.speaker_notes = update.speaker_notes.strip() if update.speaker_notes else None
        slide.status = SlideStatus.DRAFT
        slide.version += 1
        return self._presentations.save_slide(slide)

    def approve_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._require_slide(slide_id)
        slide.approve()
        return self._presentations.save_slide(slide)

    def reject_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._require_slide(slide_id)
        slide.mark_needs_revision()
        return self._presentations.save_slide(slide)

    def approve_all_slides(self, presentation_id: UUID) -> list[SlideSpec]:
        slides = self._presentations.list_slides(presentation_id)
        approved: list[SlideSpec] = []
        for slide in slides:
            slide.approve()
            approved.append(self._presentations.save_slide(slide))
        return approved

    def approve_manuscript(self, manuscript_id: UUID):
        return PresentationManuscriptService(self._session).approve(manuscript_id)

    def ensure_can_continue(self, workflow_run_id: UUID) -> PresentationReviewContext:
        run = self._workflow_runs.get_by_id(workflow_run_id)
        if run is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} not found")
        if run.status != WorkflowStatus.AWAITING_REVIEW:
            raise WorkflowError(f"Workflow run {workflow_run_id} is not awaiting review")

        if run.presentation_id is None:
            raise WorkflowError(f"Workflow run {workflow_run_id} has no presentation")

        context = self.get_review_context(run.presentation_id, workflow_run_id=run.id)
        if context is None:
            raise WorkflowError(f"Presentation {run.presentation_id} not found")

        gate = run.state.get("review_gate")
        if gate == "manuscript":
            if context.manuscript is None:
                raise WorkflowError("Manuscript is missing for review continuation")
            if context.manuscript.status != ManuscriptStatus.READY:
                raise WorkflowError("Manuscript must be approved before continuing")
        elif gate == "brief":
            if context.brief is None:
                raise WorkflowError("Brief is missing for review continuation")
            if context.brief.approval_status != ApprovalStatus.APPROVED:
                raise WorkflowError("Brief must be approved before continuing")
        elif gate == "storyline":
            if context.storyline is None:
                raise WorkflowError("Storyline is missing for review continuation")
            if context.storyline.approval_status != ApprovalStatus.APPROVED:
                raise WorkflowError("Storyline must be approved before continuing")
        elif gate == "outline":
            if context.outline is None:
                raise WorkflowError("Outline plan is missing for review continuation")
            if context.outline.approval_status != ApprovalStatus.APPROVED:
                raise WorkflowError("Outline plan must be approved before continuing")
        elif gate == "slides":
            if not context.slides:
                raise WorkflowError("Slide plan is missing for review continuation")
            if not slides_are_approved(context.slides):
                raise WorkflowError("All slides must be approved before continuing")
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

    def _require_outline(self, outline_id: UUID) -> OutlinePlan:
        outline = self._presentations.get_outline(outline_id)
        if outline is None:
            raise WorkflowError(f"Outline plan {outline_id} not found")
        return outline

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"Slide {slide_id} not found")
        return slide

    def _require_review_issue(self, issue_id: UUID) -> ReviewIssue:
        issue = self._reviews.get_by_id(issue_id)
        if issue is None:
            raise WorkflowError(f"Review issue {issue_id} not found")
        return issue


def _chapter_from_update(update: ChapterUpdate) -> Chapter:
    return Chapter(
        id=update.id.strip(),
        title=update.title.strip(),
        purpose=update.purpose.strip(),
        key_message=update.key_message.strip(),
        order=update.order,
        estimated_slide_count=update.estimated_slide_count,
    )


def _outline_section_from_update(update: OutlineSectionUpdate) -> OutlineSection:
    return OutlineSection(
        id=update.id.strip(),
        title=update.title.strip(),
        purpose=update.purpose.strip(),
        key_message=update.key_message.strip(),
        order=update.order,
        estimated_slide_count=update.estimated_slide_count,
        evidence_requirements=list(update.evidence_requirements),
        required_assets=list(update.required_assets),
        required=update.required,
        expanded=update.expanded,
        category=update.category.strip() or "general",
    )


def _parse_slide_type(value: str) -> SlideType:
    try:
        return SlideType(value.strip())
    except ValueError as exc:
        raise WorkflowError(f"Invalid slide_type: {value}") from exc
