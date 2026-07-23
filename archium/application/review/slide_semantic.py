"""Semantic layer review — image-text alignment, provenance, renovation closure."""

from __future__ import annotations

from uuid import UUID

from archium.application.chunk_models import ProjectContextBundle
from archium.application.review.base import ReviewRunnerBase
from archium.application.slide_semantic_qa_service import run_slide_semantic_qa
from archium.domain.asset import Asset
from archium.domain.document import SourceDocument
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.domain.slide_semantic_qa import SlideSemanticCheckCode
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository

_SEVERITY_MAP = {
    "critical": ReviewSeverity.CRITICAL,
    "high": ReviewSeverity.HIGH,
    "medium": ReviewSeverity.MEDIUM,
    "suggestion": ReviewSeverity.SUGGESTION,
}

_CHECK_TO_RULE: dict[str, str] = {
    SlideSemanticCheckCode.DRAWING_TOO_SMALL: ReviewRuleCode.SEMANTIC_DRAWING_TOO_SMALL,
    SlideSemanticCheckCode.DRAWING_CROP_RISK: ReviewRuleCode.SEMANTIC_DRAWING_CROP_RISK,
    SlideSemanticCheckCode.REFERENCE_ASSET_USED_AS_PROJECT_ASSET: (
        ReviewRuleCode.SEMANTIC_REFERENCE_ASSET_USED_AS_PROJECT_ASSET
    ),
    SlideSemanticCheckCode.PROJECT_ASSET_WITHOUT_SOURCE: (
        ReviewRuleCode.SEMANTIC_PROJECT_ASSET_WITHOUT_SOURCE
    ),
    SlideSemanticCheckCode.TEXT_NOT_EXPLAINING_VISUAL: (
        ReviewRuleCode.SEMANTIC_TEXT_NOT_EXPLAINING_VISUAL
    ),
    SlideSemanticCheckCode.VISUAL_WITHOUT_CAPTION: ReviewRuleCode.SEMANTIC_VISUAL_WITHOUT_CAPTION,
    SlideSemanticCheckCode.TOO_MANY_EQUAL_WEIGHT_IMAGES: (
        ReviewRuleCode.SEMANTIC_TOO_MANY_EQUAL_WEIGHT_IMAGES
    ),
    SlideSemanticCheckCode.BEFORE_AFTER_MISMATCH: ReviewRuleCode.SEMANTIC_BEFORE_AFTER_MISMATCH,
    SlideSemanticCheckCode.ISSUE_WITHOUT_EVIDENCE: ReviewRuleCode.SEMANTIC_ISSUE_WITHOUT_EVIDENCE,
    SlideSemanticCheckCode.STRATEGY_WITHOUT_TARGET: ReviewRuleCode.SEMANTIC_STRATEGY_WITHOUT_TARGET,
    SlideSemanticCheckCode.METRIC_WITHOUT_UNIT: ReviewRuleCode.SEMANTIC_METRIC_WITHOUT_UNIT,
    SlideSemanticCheckCode.EXTERNAL_FACT_WITHOUT_CITATION: (
        ReviewRuleCode.SEMANTIC_EXTERNAL_FACT_WITHOUT_CITATION
    ),
}

_CHECK_CATEGORY: dict[str, ReviewCategory] = {
    SlideSemanticCheckCode.REFERENCE_ASSET_USED_AS_PROJECT_ASSET: ReviewCategory.CITATION,
    SlideSemanticCheckCode.PROJECT_ASSET_WITHOUT_SOURCE: ReviewCategory.CITATION,
    SlideSemanticCheckCode.EXTERNAL_FACT_WITHOUT_CITATION: ReviewCategory.CITATION,
    SlideSemanticCheckCode.ISSUE_WITHOUT_EVIDENCE: ReviewCategory.CITATION,
    SlideSemanticCheckCode.STRATEGY_WITHOUT_TARGET: ReviewCategory.STRUCTURE,
    SlideSemanticCheckCode.BEFORE_AFTER_MISMATCH: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.TEXT_NOT_EXPLAINING_VISUAL: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.VISUAL_WITHOUT_CAPTION: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.DRAWING_TOO_SMALL: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.DRAWING_CROP_RISK: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.TOO_MANY_EQUAL_WEIGHT_IMAGES: ReviewCategory.VISUAL,
    SlideSemanticCheckCode.METRIC_WITHOUT_UNIT: ReviewCategory.CONSISTENCY,
}


class SlideSemanticReviewer(ReviewRunnerBase):
    """Run architecture slide semantic QA and map findings to review issues."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        context_bundle: ProjectContextBundle | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        reference_style_profile: ReferenceStyleProfile | None = None,
    ) -> list[ReviewIssue]:
        assets_by_id: dict[UUID, Asset] = {}
        documents_by_id: dict[UUID, SourceDocument] = {}
        if project_id is not None:
            assets_by_id = {
                asset.id: asset for asset in self._assets.list_by_project(project_id)
            }
            documents_by_id = {
                document.id: document
                for document in DocumentRepository(self._session).list_by_project(project_id)
            }
            if renovation_issue_map is None:
                renovation_issue_map = self._load_current_renovation_map(project_id)
            if reference_style_profile is None:
                reference_style_profile = self._load_current_reference_style(project_id)

        slides_by_id = {slide.id: slide for slide in slides}
        report = run_slide_semantic_qa(
            presentation_id,
            slides,
            project_id=project_id,
            brief=brief,
            assets_by_id=assets_by_id,
            documents_by_id=documents_by_id,
            renovation_issue_map=renovation_issue_map,
            reference_style_profile=reference_style_profile,
            has_project_sources=context_bundle is not None and bool(context_bundle.chunks),
        )

        issues: list[ReviewIssue] = []
        for finding in report.findings:
            slide = slides_by_id.get(finding.slide_id) if finding.slide_id else None
            if slide is None and finding.slide_id is None:
                continue
            if slide is None:
                continue
            rule_code = _CHECK_TO_RULE.get(finding.check_code, finding.check_code)
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.SEMANTIC,
                    category=_CHECK_CATEGORY.get(finding.check_code, ReviewCategory.OTHER),
                    severity=_SEVERITY_MAP.get(finding.severity, ReviewSeverity.MEDIUM),
                    rule_code=rule_code,
                    title=finding.title,
                    description=finding.description,
                    suggestion=finding.suggestion,
                )
            )
        return self._persist(presentation_id, issues)

    def _load_current_renovation_map(self, project_id: UUID) -> RenovationIssueMap | None:
        return ProjectRepository(self._session).get_current_renovation_issue_map(project_id)

    def _load_current_reference_style(self, project_id: UUID) -> ReferenceStyleProfile | None:
        return ProjectRepository(self._session).get_current_reference_style_profile(project_id)
