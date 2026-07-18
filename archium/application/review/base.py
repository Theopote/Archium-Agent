"""Shared review runner infrastructure."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, SlideType
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import is_auto_fixable_rule
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import AssetRepository, ReviewRepository
from archium.infrastructure.llm.base import LLMProvider

SKIPPABLE_SLIDE_TYPES = {SlideType.TITLE, SlideType.SECTION, SlideType.CLOSING}


class ReviewRunnerBase:
    """Base class for layer-specific automated reviewers."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._reviews = ReviewRepository(session)
        self._assets = AssetRepository(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def _llm_review_enabled(self) -> bool:
        return (
            self._settings.llm_professional_review_enabled
            and self._settings.llm_configured
            and self._llm is not None
        )

    def _persist(self, presentation_id: UUID, issues: list[ReviewIssue]) -> list[ReviewIssue]:
        stored: list[ReviewIssue] = []
        for issue in issues:
            stored.append(self._reviews.create(issue))
        return stored

    def _issue(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        *,
        layer: ReviewLayer,
        category: ReviewCategory,
        severity: ReviewSeverity,
        rule_code: str,
        title: str,
        description: str,
        suggestion: str | None = None,
        auto_fixable: bool | None = None,
    ) -> ReviewIssue:
        return ReviewIssue(
            presentation_id=presentation_id,
            slide_id=slide.id,
            reviewer_layer=layer,
            category=category,
            severity=severity,
            rule_code=rule_code,
            title=title,
            description=description,
            suggestion=suggestion,
            auto_fixable=is_auto_fixable_rule(rule_code) if auto_fixable is None else auto_fixable,
        )
