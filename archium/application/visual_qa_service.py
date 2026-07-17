"""Orchestrate explainable visual QA and map findings to review issues."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.asset import Asset
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, VisualType
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual_qa import VisualQAReport
from archium.infrastructure.database.repositories import AssetRepository
from archium.infrastructure.vision.analyzer import analyze_image
from archium.infrastructure.vision.image_loader import load_asset_image
from archium.logging import get_logger

logger = get_logger(__name__, operation="visual_qa")

_VISUAL_TYPE_TO_DRAWING = {
    VisualType.SITE_PLAN: "site_plan",
    VisualType.FLOOR_PLAN: "floor_plan",
    VisualType.SECTION: "section",
    VisualType.ELEVATION: "elevation",
    VisualType.DIAGRAM: "diagram",
    VisualType.MAP: "site_plan",
    VisualType.SITE_PHOTO: "photo",
    VisualType.RENDERING: "photo",
}


class VisualQAService:
    """Run lightweight image checks on slide-bound assets."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)

    def analyze_asset(self, asset: Asset) -> VisualQAReport | None:
        try:
            image = load_asset_image(asset)
        except Exception as exc:
            logger.warning("Visual QA skipped for asset %s: %s", asset.id, exc)
            return None

        return analyze_image(asset.id, asset.path, image)

    def review_slides(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        assets_by_id: dict[UUID, Asset],
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        for slide in slides:
            for index, requirement in enumerate(slide.visual_requirements):
                if requirement.type == VisualType.TEXT_ONLY:
                    continue
                asset_id = requirement.primary_asset_id
                if asset_id is None:
                    continue
                asset = assets_by_id.get(asset_id)
                if asset is None:
                    continue

                report = self.analyze_asset(asset)
                if report is None:
                    continue
                issues.extend(
                    self._issues_for_requirement(
                        presentation_id,
                        slide,
                        requirement,
                        asset,
                        report,
                        requirement_index=index,
                    )
                )
        return issues

    def _issues_for_requirement(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        requirement: VisualRequirement,
        asset: Asset,
        report: VisualQAReport,
        *,
        requirement_index: int,
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        prefix = f"第 {slide.order + 1} 页素材「{asset.filename}」"

        dimensions = report.check("image_dimensions")
        if dimensions is not None and not dimensions.passed:
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.MEDIUM,
                    rule_code=ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL,
                    title="图像分辨率不足",
                    description=f"{prefix}：{dimensions.summary}",
                    suggestion="替换更高分辨率素材或裁剪重点区域。",
                    evidence=dimensions.evidence,
                )
            )

        margins = report.check("blank_margins")
        if margins is not None and not margins.passed:
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.SUGGESTION,
                    rule_code=ReviewRuleCode.VISUAL_EXCESSIVE_MARGINS,
                    title="图像空白边距过大",
                    description=f"{prefix}：{margins.summary}",
                    suggestion="裁剪空白边距以提升有效图面占比。",
                    evidence=margins.evidence,
                )
            )

        colors = report.check("dominant_colors")
        if colors is not None and not colors.passed:
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.SUGGESTION,
                    rule_code=ReviewRuleCode.VISUAL_LOW_COLOR_CONTRAST,
                    title="图像对比度偏低",
                    description=f"{prefix}：{colors.summary}",
                    suggestion="检查流线颜色或标注是否足够清晰。",
                    evidence=colors.evidence,
                )
            )

        clipping = report.check("edge_clipping")
        if clipping is not None and not clipping.passed:
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.MEDIUM,
                    rule_code=ReviewRuleCode.VISUAL_CONTENT_CLIPPED,
                    title="图像可能被裁切",
                    description=f"{prefix}：{clipping.summary}",
                    suggestion="确认图纸边缘内容完整，必要时重新导出或调整裁剪。",
                    evidence=clipping.evidence,
                )
            )

        text_density = report.check("text_density")
        if text_density is not None and not text_density.passed:
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.LAYOUT,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.SUGGESTION,
                    rule_code=ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY,
                    title="图纸文字密度过高",
                    description=f"{prefix}：{text_density.summary}",
                    suggestion="检查标注字号是否过小，必要时拆分页面或放大图面。",
                    evidence=text_density.evidence,
                )
            )

        if requirement.type in {VisualType.SITE_PLAN, VisualType.MAP}:
            north = report.check("north_arrow")
            if north is not None and not north.passed:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.ARCHITECTURAL,
                        category=ReviewCategory.VISUAL,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW,
                        title="图像未检测到指北针",
                        description=f"{prefix}：{north.summary}",
                        suggestion="在总平面图中补充指北针或明确北向标注。",
                        evidence=north.evidence,
                    )
                )

        if requirement.type in {VisualType.SITE_PLAN, VisualType.DIAGRAM, VisualType.MAP}:
            context = " ".join((slide.title, slide.message, requirement.description)).lower()
            if any(keyword in context for keyword in ("流线", "交通", "traffic", "circulation", "图例")):
                legend = report.check("legend_region")
                if legend is not None and not legend.passed:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.ARCHITECTURAL,
                            category=ReviewCategory.VISUAL,
                            severity=ReviewSeverity.SUGGESTION,
                            rule_code=ReviewRuleCode.VISUAL_MISSING_LEGEND,
                            title="图像未检测到图例区域",
                            description=f"{prefix}：{legend.summary}",
                            suggestion="补充流线颜色图例，确保受众能读懂颜色含义。",
                            evidence=legend.evidence,
                        )
                    )

        expected = _VISUAL_TYPE_TO_DRAWING.get(requirement.type)
        if (
            expected is not None
            and report.drawing_type is not None
            and report.drawing_type != expected
            and (report.drawing_type_confidence or 0.0) >= 0.55
        ):
            classifier = report.check("drawing_classifier")
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=ReviewLayer.ARCHITECTURAL,
                    category=ReviewCategory.VISUAL,
                    severity=ReviewSeverity.MEDIUM,
                    rule_code=ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH,
                    title="图像类型与页面需求不一致",
                    description=(
                        f"{prefix}：页面要求 {requirement.type.value}，"
                        f"图像分类倾向 {report.drawing_type}（置信度 {report.drawing_type_confidence:.2f}）。"
                    ),
                    suggestion="确认是否绑定了错误图纸，或在 Asset Board 中更换素材。",
                    evidence=classifier.evidence if classifier else {},
                )
            )

        if not issues:
            logger.debug(
                "Visual QA passed for slide %s requirement %d (%s)",
                slide.id,
                requirement_index,
                asset.filename,
            )
        return issues

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
        evidence: dict[str, object] | None = None,
    ) -> ReviewIssue:
        if evidence:
            description = f"{description}（依据：{self._format_evidence(evidence)}）"
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
        )

    @staticmethod
    def _format_evidence(evidence: dict[str, object]) -> str:
        parts: list[str] = []
        for key, value in evidence.items():
            if key in {"dominant_colors", "scores", "margin_contrast_by_edge"}:
                continue
            parts.append(f"{key}={value}")
        return "；".join(parts[:4])
