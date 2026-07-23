"""Deck-level narrative coherence review — maps findings to ReviewIssue."""

from __future__ import annotations

from uuid import UUID

from archium.application.deck_coherence_qa_service import DeckCoherenceQAService
from archium.application.review.base import ReviewRunnerBase
from archium.domain.deck_coherence import (
    DECK_CLOSING_WITHOUT_DECISION,
    DECK_DUPLICATE_KEY_POINT,
    DECK_DUPLICATE_MESSAGE,
    DECK_NO_ADVANCEMENT,
    DECK_RESOLUTION_UNSUPPORTED,
    DECK_STAGE_REGRESSION,
    DECK_STRATEGY_UNANCHORED,
    DECK_STRATEGY_WITHOUT_PROBLEM,
    DECK_WEAK_SECTION_EVIDENCE,
)
from archium.domain.enums import ReviewCategory, ReviewLayer
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.domain.visual.severity import layout_to_review

_RULE_MAP = {
    DECK_DUPLICATE_MESSAGE: ReviewRuleCode.DECK_DUPLICATE_MESSAGE,
    DECK_DUPLICATE_KEY_POINT: ReviewRuleCode.DECK_DUPLICATE_KEY_POINT,
    DECK_STRATEGY_WITHOUT_PROBLEM: ReviewRuleCode.DECK_STRATEGY_WITHOUT_PROBLEM,
    DECK_CLOSING_WITHOUT_DECISION: ReviewRuleCode.DECK_CLOSING_WITHOUT_DECISION,
    DECK_WEAK_SECTION_EVIDENCE: ReviewRuleCode.DECK_WEAK_SECTION_EVIDENCE,
    DECK_NO_ADVANCEMENT: ReviewRuleCode.DECK_NO_ADVANCEMENT,
    DECK_STRATEGY_UNANCHORED: ReviewRuleCode.DECK_STRATEGY_UNANCHORED,
    DECK_STAGE_REGRESSION: ReviewRuleCode.DECK_STAGE_REGRESSION,
    DECK_RESOLUTION_UNSUPPORTED: ReviewRuleCode.DECK_RESOLUTION_UNSUPPORTED,
}


class DeckCoherenceReviewer(ReviewRunnerBase):
    """Cross-slide argument / repetition / section-closure QA."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        outline: OutlinePlan | None = None,
        storyline: Storyline | None = None,
        manuscript: PresentationManuscript | None = None,
    ) -> list[ReviewIssue]:
        if not slides:
            return []
        report = DeckCoherenceQAService().evaluate(
            slides,
            outline=outline,
            storyline=storyline,
            manuscript=manuscript,
        )
        slides_by_id = {str(slide.id): slide for slide in slides}
        issues: list[ReviewIssue] = []
        for finding in report.findings:
            anchor = slides[0]
            for slide_id in finding.slide_ids:
                if slide_id in slides_by_id:
                    anchor = slides_by_id[slide_id]
                    break
            issues.append(
                self._issue(
                    presentation_id,
                    anchor,
                    layer=ReviewLayer.CONTENT,
                    category=ReviewCategory.CONSISTENCY,
                    severity=layout_to_review(finding.severity),
                    rule_code=_RULE_MAP.get(finding.rule_code, finding.rule_code),
                    title="Deck 论证一致性",
                    description=finding.message,
                    suggestion=finding.suggestion,
                )
            )
        return self._persist(presentation_id, issues)
