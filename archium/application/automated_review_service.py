"""Automated content and professional review for presentation slides."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.domain.enums import (
    ReviewCategory,
    ReviewSeverity,
    SlideType,
    VisualType,
)
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import ReviewRepository


class AutomatedReviewService:
    """Run rule-based content and professional QA checks."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._reviews = ReviewRepository(session)

    def run_content_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        """Check slide copy, citations, and length."""
        has_sources = context_bundle is not None and bool(context_bundle.chunks)
        skippable = {SlideType.TITLE, SlideType.SECTION, SlideType.CLOSING}
        issues: list[ReviewIssue] = []

        for slide in slides:
            if not slide.title.strip():
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        category=ReviewCategory.CONTENT,
                        severity=ReviewSeverity.HIGH,
                        title="缺少标题",
                        description=f"第 {slide.order + 1} 页缺少标题。",
                    )
                )
            if not slide.message.strip() and slide.slide_type not in skippable:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        category=ReviewCategory.CONTENT,
                        severity=ReviewSeverity.HIGH,
                        title="缺少核心信息",
                        description=f"第 {slide.order + 1} 页「{slide.title}」缺少核心结论。",
                    )
                )
            if has_sources and slide.slide_type not in skippable and not slide.source_citations:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        category=ReviewCategory.CITATION,
                        severity=ReviewSeverity.MEDIUM,
                        title="缺少引用来源",
                        description=f"第 {slide.order + 1} 页「{slide.title}」未关联项目资料。",
                        suggestion="补充 chunk 引用或上传对应图纸/照片。",
                    )
                )
            if len(slide.key_points) > 5:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        category=ReviewCategory.LENGTH,
                        severity=ReviewSeverity.SUGGESTION,
                        title="要点过多",
                        description=f"第 {slide.order + 1} 页要点超过 5 条，建议精简。",
                    )
                )

        return self._persist(presentation_id, issues)

    def run_professional_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
    ) -> list[ReviewIssue]:
        """Check structure, coverage, and visual readiness."""
        issues: list[ReviewIssue] = []

        if brief is not None and slides:
            target = brief.target_slide_count
            actual = len(slides)
            if target > 0 and abs(actual - target) / target > 0.25:
                issues.append(
                    ReviewIssue(
                        presentation_id=presentation_id,
                        category=ReviewCategory.STRUCTURE,
                        severity=ReviewSeverity.MEDIUM,
                        title="页数偏离目标",
                        description=(
                            f"当前 {actual} 页，Brief 目标 {target} 页，偏差超过 25%。"
                        ),
                        suggestion="调整章节分配或合并/拆分页面。",
                    )
                )

            if brief.required_sections:
                titles = " ".join(slide.title for slide in slides)
                for section in brief.required_sections:
                    if section.strip() and section.strip() not in titles:
                        issues.append(
                            ReviewIssue(
                                presentation_id=presentation_id,
                                category=ReviewCategory.COVERAGE,
                                severity=ReviewSeverity.HIGH,
                                title="必要章节未覆盖",
                                description=f"Brief 要求包含「{section}」，当前 Slide 标题中未找到。",
                            )
                        )

        if storyline is not None and slides:
            chapter_ids = {chapter.id for chapter in storyline.chapters}
            slide_chapters = {slide.chapter_id for slide in slides}
            missing = chapter_ids - slide_chapters
            for chapter_id in sorted(missing):
                issues.append(
                    ReviewIssue(
                        presentation_id=presentation_id,
                        category=ReviewCategory.STRUCTURE,
                        severity=ReviewSeverity.MEDIUM,
                        title="章节缺少对应页面",
                        description=f"Storyline 章节 {chapter_id} 未分配任何 Slide。",
                    )
                )

        for slide in slides:
            for requirement in slide.visual_requirements:
                if requirement.type == VisualType.TEXT_ONLY:
                    continue
                if requirement.required and not requirement.preferred_asset_ids:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            category=ReviewCategory.VISUAL,
                            severity=ReviewSeverity.MEDIUM,
                            title="缺少匹配素材",
                            description=(
                                f"第 {slide.order + 1} 页需要 {requirement.type.value} 类视觉，"
                                "但未匹配到项目素材。"
                            ),
                            suggestion="上传图纸/照片或在审核阶段手动指定素材。",
                        )
                    )

        return self._persist(presentation_id, issues)

    def summarize_for_slides(self, issues: list[ReviewIssue]) -> list[str]:
        return [f"{issue.title}: {issue.description}" for issue in issues if issue.slide_id]

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
        category: ReviewCategory,
        severity: ReviewSeverity,
        title: str,
        description: str,
        suggestion: str | None = None,
    ) -> ReviewIssue:
        return ReviewIssue(
            presentation_id=presentation_id,
            slide_id=slide.id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            suggestion=suggestion,
        )
