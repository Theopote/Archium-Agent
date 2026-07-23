"""Scene + post-render QA reviewers (WP H)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.application.review.base import ReviewRunnerBase
from archium.application.visual.post_render_qa_service import run_post_render_qa
from archium.application.visual.scene_semantic_qa_service import run_scene_semantic_qa
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.domain.visual.quality_issue_catalog import default_severity_for_auto_code
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_qa import PostRenderCheckCode, SceneSemanticCheckCode
from archium.domain.visual.severity import (
    coerce_review_severity_label,
    gate_to_review,
    review_rank,
)

_SCENE_CHECK_TO_RULE: dict[str, str] = {
    SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN: (
        ReviewRuleCode.SEMANTIC_DRAWING_COVER_MODE_FORBIDDEN
    ),
    SceneSemanticCheckCode.AI_IMAGE_PRESENTED_AS_REAL_PROJECT: (
        ReviewRuleCode.SEMANTIC_AI_IMAGE_PRESENTED_AS_REAL_PROJECT
    ),
    SceneSemanticCheckCode.STOCK_IMAGE_PRESENTED_AS_PROJECT: (
        ReviewRuleCode.SEMANTIC_STOCK_IMAGE_PRESENTED_AS_PROJECT
    ),
    SceneSemanticCheckCode.IMAGE_NOT_RENDERED: ReviewRuleCode.SEMANTIC_IMAGE_NOT_RENDERED,
    SceneSemanticCheckCode.FONT_TOO_SMALL: ReviewRuleCode.SEMANTIC_FONT_TOO_SMALL,
    SceneSemanticCheckCode.TEXT_OVERFLOW: ReviewRuleCode.SEMANTIC_TEXT_OVERFLOW,
    SceneSemanticCheckCode.CAPTION_MISSING: ReviewRuleCode.SEMANTIC_CAPTION_MISSING,
    SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH: (
        ReviewRuleCode.SEMANTIC_SCENE_PPTX_NODE_MISMATCH
    ),
    SceneSemanticCheckCode.FONT_FALLBACK_CHANGED_LAYOUT: (
        ReviewRuleCode.SEMANTIC_FONT_FALLBACK_CHANGED_LAYOUT
    ),
}

_POST_CHECK_TO_RULE: dict[str, str] = {
    PostRenderCheckCode.BLANK_PAGE: ReviewRuleCode.POST_RENDER_BLANK_PAGE,
    PostRenderCheckCode.BLACK_BLOCK: ReviewRuleCode.POST_RENDER_BLACK_BLOCK,
    PostRenderCheckCode.IMAGE_NOT_LOADED: ReviewRuleCode.POST_RENDER_IMAGE_NOT_LOADED,
    PostRenderCheckCode.DUPLICATE_PAGE: ReviewRuleCode.POST_RENDER_DUPLICATE_PAGE,
    PostRenderCheckCode.ALL_PAGES_IDENTICAL: ReviewRuleCode.POST_RENDER_ALL_PAGES_IDENTICAL,
    PostRenderCheckCode.DRAWING_BLUR: ReviewRuleCode.POST_RENDER_DRAWING_BLUR,
    PostRenderCheckCode.SEVERE_STRETCH: ReviewRuleCode.POST_RENDER_SEVERE_STRETCH,
    PostRenderCheckCode.PNG_PPTX_DIFF: ReviewRuleCode.POST_RENDER_PNG_PPTX_DIFF,
}

_SCENE_CATEGORY: dict[str, ReviewCategory] = {
    SceneSemanticCheckCode.AI_IMAGE_PRESENTED_AS_REAL_PROJECT: ReviewCategory.CITATION,
    SceneSemanticCheckCode.STOCK_IMAGE_PRESENTED_AS_PROJECT: ReviewCategory.CITATION,
    SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN: ReviewCategory.VISUAL,
    SceneSemanticCheckCode.IMAGE_NOT_RENDERED: ReviewCategory.VISUAL,
    SceneSemanticCheckCode.FONT_TOO_SMALL: ReviewCategory.VISUAL,
    SceneSemanticCheckCode.TEXT_OVERFLOW: ReviewCategory.VISUAL,
    SceneSemanticCheckCode.CAPTION_MISSING: ReviewCategory.VISUAL,
    SceneSemanticCheckCode.SCENE_PPTX_NODE_MISMATCH: ReviewCategory.CONSISTENCY,
    SceneSemanticCheckCode.FONT_FALLBACK_CHANGED_LAYOUT: ReviewCategory.VISUAL,
}


class SceneSemanticReviewer(ReviewRunnerBase):
    """Map RenderScene semantic QA findings to review issues."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        scenes: list[RenderScene],
        *,
        project_id: UUID | None = None,
        pptx_paths_by_slide: dict[UUID, Path] | None = None,
    ) -> list[ReviewIssue]:
        if not scenes:
            return []
        slides_by_id = {slide.id: slide for slide in slides}
        orders = {slide.id: slide.order for slide in slides}
        report = run_scene_semantic_qa(
            presentation_id,
            scenes,
            project_id=project_id,
            pptx_paths_by_slide=pptx_paths_by_slide,
            slide_orders=orders,
        )
        issues: list[ReviewIssue] = []
        for finding in report.findings:
            slide = slides_by_id.get(finding.slide_id) if finding.slide_id else None
            if slide is None:
                continue
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.SEMANTIC,
                    category=_SCENE_CATEGORY.get(finding.check_code, ReviewCategory.VISUAL),
                    severity=_review_severity_for_check(finding.check_code, finding.severity),
                    rule_code=_SCENE_CHECK_TO_RULE.get(finding.check_code, finding.check_code),
                    title=finding.title,
                    description=finding.description,
                    suggestion=finding.suggestion,
                )
            )
        return self._persist(presentation_id, issues)


class PostRenderReviewer(ReviewRunnerBase):
    """Map screenshot QA findings to review issues."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        screenshots: list[tuple[UUID, Path]],
        *,
        project_id: UUID | None = None,
        scenes_by_slide: dict[UUID, RenderScene] | None = None,
        pptx_screenshots: dict[UUID, Path] | None = None,
    ) -> list[ReviewIssue]:
        if not screenshots:
            return []
        slides_by_id = {slide.id: slide for slide in slides}
        orders = {slide.id: slide.order for slide in slides}
        report = run_post_render_qa(
            presentation_id,
            screenshots,
            project_id=project_id,
            scenes_by_slide=scenes_by_slide,
            pptx_screenshots=pptx_screenshots,
            slide_orders=orders,
        )
        issues: list[ReviewIssue] = []
        for finding in report.findings:
            slide = slides_by_id.get(finding.slide_id) if finding.slide_id else None
            if slide is None:
                continue
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=_review_severity_for_check(finding.check_code, finding.severity),
                    rule_code=_POST_CHECK_TO_RULE.get(finding.check_code, finding.check_code),
                    title=finding.title,
                    description=finding.description,
                    suggestion=finding.suggestion,
                )
            )
        return self._persist(presentation_id, issues)


def _review_severity_for_check(check_code: str, finding_severity: str) -> ReviewSeverity:
    """Prefer catalog severity; never demote below the finding's own severity."""
    catalog = gate_to_review(default_severity_for_auto_code(check_code))
    emitted = coerce_review_severity_label(finding_severity)
    if review_rank(catalog) >= review_rank(emitted):
        return catalog
    return emitted
