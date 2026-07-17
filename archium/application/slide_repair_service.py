"""Repair individual slides based on automated review feedback."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import sanitize_slide_message
from archium.config.settings import Settings, get_settings
from archium.domain.enums import ReviewCategory, ReviewSeverity, ReviewStatus
from archium.domain.presentation import PresentationBrief
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository, ReviewRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import SlideRepairDraft
from archium.logging import get_logger
from archium.prompts.slide_repair import (
    SLIDE_REPAIR_SYSTEM_PROMPT,
    build_slide_repair_user_prompt,
)

logger = get_logger(__name__, operation="slide_repair")

_REPAIRABLE_CATEGORIES = {
    ReviewCategory.CONTENT,
    ReviewCategory.CITATION,
    ReviewCategory.LENGTH,
    ReviewCategory.CONSISTENCY,
}
_REPAIRABLE_SEVERITIES = {ReviewSeverity.CRITICAL, ReviewSeverity.HIGH}


class SlideRepairService:
    """LLM-assisted per-slide fixes for open review issues."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._presentations = PresentationRepository(session)
        self._reviews = ReviewRepository(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def repair_slides(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        issues: list[ReviewIssue],
        *,
        brief: PresentationBrief | None = None,
    ) -> tuple[list[SlideSpec], int]:
        """Repair slide-level issues and return updated slides plus repair count."""
        if not self._settings.slide_repair_enabled or self._llm is None:
            return slides, 0

        slides_by_id = {slide.id: slide for slide in slides}
        issues_by_slide: dict[UUID, list[ReviewIssue]] = {}
        for issue in issues:
            if issue.status != ReviewStatus.OPEN:
                continue
            if issue.slide_id is None:
                continue
            if issue.category not in _REPAIRABLE_CATEGORIES:
                continue
            if issue.severity not in _REPAIRABLE_SEVERITIES:
                continue
            issues_by_slide.setdefault(issue.slide_id, []).append(issue)

        if not issues_by_slide:
            return slides, 0

        brief_summary = (
            f"标题: {brief.title}\n核心信息: {brief.core_message}"
            if brief is not None
            else "无 Brief"
        )
        repaired = 0
        updated_slides = list(slides)

        for slide_id, slide_issues in issues_by_slide.items():
            slide = slides_by_id.get(slide_id)
            if slide is None:
                continue
            try:
                draft = self._llm.generate_structured(
                    LLMRequest(
                        system_prompt=SLIDE_REPAIR_SYSTEM_PROMPT,
                        user_prompt=build_slide_repair_user_prompt(
                            slide_summary=_slide_summary(slide),
                            issue_summary=_issue_summary(slide_issues),
                            brief_summary=brief_summary,
                        ),
                        model=self._settings.llm_model,
                        temperature=0.3,
                        json_mode=True,
                    ),
                    SlideRepairDraft,
                )
            except Exception as exc:
                logger.warning("Slide repair failed for slide %s: %s", slide_id, exc)
                continue

            slide.title = draft.title.strip() or slide.title
            slide.message = sanitize_slide_message(draft.message)
            slide.key_points = list(draft.key_points[:5])
            saved = self._presentations.save_slide(slide)
            slides_by_id[slide_id] = saved
            updated_slides = [slides_by_id.get(item.id, item) for item in updated_slides]

            for issue in slide_issues:
                issue.resolve()
                self._reviews.update(issue)
            repaired += 1

        logger.info("Repaired %d slide(s) for presentation %s", repaired, presentation_id)
        return updated_slides, repaired


def _slide_summary(slide: SlideSpec) -> str:
    points = "\n".join(f"- {point}" for point in slide.key_points) or "（无要点）"
    return (
        f"第 {slide.order + 1} 页\n"
        f"标题: {slide.title}\n"
        f"核心信息: {slide.message}\n"
        f"要点:\n{points}"
    )


def _issue_summary(issues: list[ReviewIssue]) -> str:
    return "\n".join(
        f"- [{issue.severity.value}] {issue.title}: {issue.description}"
        + (f"（建议：{issue.suggestion}）" if issue.suggestion else "")
        for issue in issues
    )
