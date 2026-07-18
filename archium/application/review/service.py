"""Facade for automated four-layer presentation review."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.application.review.architectural import ArchitecturalReviewer
from archium.application.review.content import ContentReviewer
from archium.application.review.evidence import EvidenceReviewer
from archium.application.review.layout import LayoutReviewer
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.infrastructure.llm.base import LLMProvider


class AutomatedReviewService:
    """Run rule-based and optional LLM-assisted presentation QA checks."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self._content = ContentReviewer(session, llm=llm, settings=resolved_settings)
        self._evidence = EvidenceReviewer(session, llm=llm, settings=resolved_settings)
        self._architectural = ArchitecturalReviewer(session, llm=llm, settings=resolved_settings)
        self._layout = LayoutReviewer(session, llm=llm, settings=resolved_settings)

    def run_content_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
    ) -> list[ReviewIssue]:
        return self._content.run(presentation_id, slides, brief=brief)

    def run_evidence_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        return self._evidence.run(presentation_id, slides, context_bundle=context_bundle)

    def run_architectural_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
    ) -> list[ReviewIssue]:
        return self._architectural.run(
            presentation_id,
            slides,
            brief=brief,
            storyline=storyline,
        )

    def run_layout_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        return self._layout.run(
            presentation_id,
            slides,
            project_id=project_id,
            brief=brief,
            storyline=storyline,
            context_bundle=context_bundle,
        )

    def run_professional_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
        project_id: UUID | None = None,
    ) -> list[ReviewIssue]:
        """Run all four review layers (backward-compatible aggregate entry point)."""
        issues: list[ReviewIssue] = []
        issues.extend(self.run_content_review(presentation_id, slides, brief=brief))
        issues.extend(
            self.run_evidence_review(presentation_id, slides, context_bundle=context_bundle)
        )
        issues.extend(
            self.run_architectural_review(
                presentation_id,
                slides,
                brief=brief,
                storyline=storyline,
            )
        )
        issues.extend(
            self.run_layout_review(
                presentation_id,
                slides,
                project_id=project_id,
                brief=brief,
                storyline=storyline,
                context_bundle=context_bundle,
            )
        )
        return issues

    def summarize_for_slides(self, issues: list[ReviewIssue]) -> list[str]:
        return [f"{issue.title}: {issue.description}" for issue in issues if issue.slide_id]
