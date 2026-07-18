"""Content layer review — copy clarity, repetition, Brief alignment."""

from __future__ import annotations

import re
from uuid import UUID

from archium.application.review.base import SKIPPABLE_SLIDE_TYPES, ReviewRunnerBase
from archium.application.review.llm_helpers import run_llm_brief_alignment
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity
from archium.domain.presentation import PresentationBrief
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec


class ContentReviewer(ReviewRunnerBase):
    """Check slide copy clarity, repetition, and Brief alignment."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        title_counts: dict[str, int] = {}

        for slide in slides:
            title_key = slide.title.strip()
            if title_key:
                title_counts[title_key] = title_counts.get(title_key, 0) + 1

            if not title_key:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.CONTENT,
                        category=ReviewCategory.CONTENT,
                        severity=ReviewSeverity.HIGH,
                        rule_code=ReviewRuleCode.CONTENT_MISSING_TITLE,
                        title="缺少标题",
                        description=f"第 {slide.order + 1} 页缺少标题。",
                    )
                )
            if not slide.message.strip() and slide.slide_type not in SKIPPABLE_SLIDE_TYPES:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.CONTENT,
                        category=ReviewCategory.CONTENT,
                        severity=ReviewSeverity.CRITICAL,
                        rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
                        title="缺少核心信息",
                        description=f"第 {slide.order + 1} 页「{slide.title}」缺少核心结论。",
                    )
                )
            if (
                slide.message.strip()
                and slide.slide_type not in SKIPPABLE_SLIDE_TYPES
                and len(slide.message.strip()) < 8
            ):
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.CONTENT,
                        category=ReviewCategory.CONTENT,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.CONTENT_MESSAGE_TOO_SHORT,
                        title="结论表述过于简略",
                        description=(
                            f"第 {slide.order + 1} 页「{slide.title}」核心结论过短，"
                            "建议补充可决策的完整表述。"
                        ),
                    )
                )

        for title, count in title_counts.items():
            if count > 1:
                issues.append(
                    ReviewIssue(
                        presentation_id=presentation_id,
                        reviewer_layer=ReviewLayer.CONTENT,
                        category=ReviewCategory.CONSISTENCY,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.CONTENT_DUPLICATE_TITLE,
                        title="标题重复",
                        description=f"标题「{title}」在 {count} 页中重复出现，建议区分章节重点。",
                    )
                )

        if brief is not None and brief.core_message.strip() and slides:
            alignment_issue = self._check_brief_alignment(presentation_id, slides, brief)
            if alignment_issue is not None:
                issues.append(alignment_issue)

        return self._persist(presentation_id, issues)

    def _check_brief_alignment(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        brief: PresentationBrief,
    ) -> ReviewIssue | None:
        if self._llm_review_enabled() and self._llm is not None:
            llm_issue, llm_succeeded = run_llm_brief_alignment(
                self._llm,
                self._settings,
                presentation_id,
                brief,
                slides,
            )
            if llm_succeeded:
                return llm_issue
        return self._rule_based_brief_alignment(presentation_id, brief, slides)

    def _rule_based_brief_alignment(
        self,
        presentation_id: UUID,
        brief: PresentationBrief,
        slides: list[SlideSpec],
    ) -> ReviewIssue | None:
        tokens = [
            token
            for token in re.split(r"[\s，,、；;。.]+", brief.core_message.strip())
            if len(token) >= 2
        ]
        combined = " ".join(slide.message for slide in slides)
        if tokens and not any(token in combined for token in tokens[:5]):
            return ReviewIssue(
                presentation_id=presentation_id,
                reviewer_layer=ReviewLayer.CONTENT,
                category=ReviewCategory.COVERAGE,
                severity=ReviewSeverity.MEDIUM,
                rule_code=ReviewRuleCode.CONTENT_BRIEF_CORE_NOT_REFLECTED,
                title="Brief 核心信息未体现",
                description=(
                    f"Brief 核心信息「{brief.core_message}」"
                    "未在 Slide 结论中找到明显呼应。"
                ),
                suggestion="调整各页结论，确保与 Brief 核心信息一致。",
            )
        return None
