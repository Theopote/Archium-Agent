"""Orchestrate explainable visual QA and map findings to review issues."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual_qa_policy import (
    DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE,
    decide_check_issue,
)
from archium.domain.asset import Asset
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, VisualType
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual_qa import VisualQACheck, VisualQAReport
from archium.infrastructure.database.repositories import AssetRepository, VisualQAReportRepository
from archium.infrastructure.vision.analyzer import analyze_image
from archium.infrastructure.vision.analyzer_version import ANALYZER_VERSION
from archium.infrastructure.vision.asset_fingerprint import asset_content_hash
from archium.infrastructure.vision.asset_load_errors import rule_code_for_asset_load_error
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

_CHECK_ISSUE_SPECS: dict[str, tuple[str, str, str, ReviewLayer, ReviewCategory, ReviewSeverity]] = {
    "image_dimensions": (
        ReviewRuleCode.VISUAL_DIMENSIONS_TOO_SMALL,
        "图像分辨率不足",
        "替换更高分辨率素材或裁剪重点区域。",
        ReviewLayer.LAYOUT,
        ReviewCategory.VISUAL,
        ReviewSeverity.MEDIUM,
    ),
    "blank_margins": (
        ReviewRuleCode.VISUAL_EXCESSIVE_MARGINS,
        "图像空白边距过大",
        "裁剪空白边距以提升有效图面占比。",
        ReviewLayer.LAYOUT,
        ReviewCategory.VISUAL,
        ReviewSeverity.SUGGESTION,
    ),
    "dominant_colors": (
        ReviewRuleCode.VISUAL_LOW_COLOR_CONTRAST,
        "图像对比度偏低",
        "检查流线颜色或标注是否足够清晰。",
        ReviewLayer.LAYOUT,
        ReviewCategory.VISUAL,
        ReviewSeverity.SUGGESTION,
    ),
    "edge_clipping": (
        ReviewRuleCode.VISUAL_CONTENT_CLIPPED,
        "图像可能被裁切",
        "确认图纸边缘内容完整，必要时重新导出或调整裁剪。",
        ReviewLayer.LAYOUT,
        ReviewCategory.VISUAL,
        ReviewSeverity.MEDIUM,
    ),
    "text_density": (
        ReviewRuleCode.VISUAL_HIGH_TEXT_DENSITY,
        "图纸文字密度过高",
        "检查标注字号是否过小，必要时拆分页面或放大图面。",
        ReviewLayer.LAYOUT,
        ReviewCategory.VISUAL,
        ReviewSeverity.SUGGESTION,
    ),
    "north_arrow": (
        ReviewRuleCode.VISUAL_MISSING_NORTH_ARROW,
        "图像未检测到指北针",
        "在总平面图中补充指北针或明确北向标注。",
        ReviewLayer.ARCHITECTURAL,
        ReviewCategory.VISUAL,
        ReviewSeverity.MEDIUM,
    ),
    "legend_region": (
        ReviewRuleCode.VISUAL_MISSING_LEGEND,
        "图像未检测到图例区域",
        "补充流线颜色图例，确保受众能读懂颜色含义。",
        ReviewLayer.ARCHITECTURAL,
        ReviewCategory.VISUAL,
        ReviewSeverity.SUGGESTION,
    ),
}

_ASSET_LOAD_RULE_CODES = frozenset(
    {
        ReviewRuleCode.VISUAL_ASSET_UNREADABLE,
        ReviewRuleCode.VISUAL_ASSET_FILE_NOT_FOUND,
        ReviewRuleCode.VISUAL_ASSET_FORMAT_UNSUPPORTED,
        ReviewRuleCode.VISUAL_ASSET_DECODE_FAILED,
        ReviewRuleCode.VISUAL_ASSET_PERMISSION_DENIED,
        ReviewRuleCode.VISUAL_ASSET_RECORD_MISSING,
    }
)


def asset_load_rule_codes() -> frozenset[str]:
    """Rule codes for asset load / binding failures that may block export."""
    return _ASSET_LOAD_RULE_CODES


class VisualQAService:
    """Run lightweight image checks on slide-bound assets."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)
        self._reports = VisualQAReportRepository(session)

    def _get_or_analyze_report(
        self,
        asset: Asset,
        report_cache: dict[UUID, VisualQAReport | Exception],
    ) -> VisualQAReport:
        cached = report_cache.get(asset.id)
        if isinstance(cached, VisualQAReport):
            return cached
        if isinstance(cached, Exception):
            raise cached

        file_hash = asset_content_hash(asset.path)
        stored = self._reports.get_cached(
            asset.id,
            file_hash=file_hash,
            analyzer_version=ANALYZER_VERSION,
        )
        if stored is not None:
            report_cache[asset.id] = stored
            return stored

        image = load_asset_image(asset)
        report = analyze_image(asset.id, asset.path, image).model_copy(
            update={"file_hash": file_hash, "analyzer_version": ANALYZER_VERSION}
        )
        saved = self._reports.save(
            report,
            file_hash=file_hash,
            analyzer_version=ANALYZER_VERSION,
        )
        report_cache[asset.id] = saved
        return saved

    def analyze_asset(self, asset: Asset) -> VisualQAReport:
        """Load and analyze one asset image; raises on load/analyze failure."""
        cache: dict[UUID, VisualQAReport | Exception] = {}
        return self._get_or_analyze_report(asset, cache)

    def review_slides(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        assets_by_id: dict[UUID, Asset],
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        report_cache: dict[UUID, VisualQAReport | Exception] = {}

        for slide in slides:
            for index, requirement in enumerate(slide.visual_requirements):
                if requirement.type == VisualType.TEXT_ONLY:
                    continue

                bound_ids = requirement.bound_asset_ids()
                if not bound_ids:
                    continue

                for asset_id in bound_ids:
                    asset = assets_by_id.get(asset_id)
                    if asset is None:
                        issues.append(
                            self._asset_binding_issue(
                                presentation_id,
                                slide,
                                requirement,
                                asset_id=asset_id,
                                rule_code=ReviewRuleCode.VISUAL_ASSET_RECORD_MISSING,
                                title="素材记录缺失",
                                description=(
                                    f"第 {slide.order + 1} 页绑定了素材 {asset_id}，"
                                    "但项目素材库中找不到对应记录。"
                                ),
                            )
                        )
                        continue

                    if asset_id not in report_cache:
                        try:
                            report_cache[asset_id] = self._get_or_analyze_report(asset, report_cache)
                        except Exception as exc:
                            logger.warning(
                                "Visual QA failed to load asset %s (%s): %s",
                                asset.id,
                                asset.filename,
                                exc,
                            )
                            report_cache[asset_id] = exc

                    cached = report_cache[asset_id]
                    if isinstance(cached, Exception):
                        issues.append(
                            self._asset_load_issue(
                                presentation_id,
                                slide,
                                requirement,
                                asset,
                                cached,
                            )
                        )
                        continue

                    issues.extend(
                        self._issues_for_requirement(
                            presentation_id,
                            slide,
                            requirement,
                            asset,
                            cached,
                            requirement_index=index,
                        )
                    )
        return issues

    def _asset_binding_issue(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        requirement: VisualRequirement,
        *,
        asset_id: UUID,
        rule_code: str,
        title: str,
        description: str,
    ) -> ReviewIssue:
        required_note = "（必需素材）" if requirement.required else ""
        return self._issue(
            presentation_id,
            slide,
            layer=ReviewLayer.LAYOUT,
            category=ReviewCategory.VISUAL,
            severity=self._asset_failure_severity(requirement),
            rule_code=rule_code,
            title=title,
            description=f"{description}{required_note}",
            suggestion="在 Asset Board 中重新绑定有效素材，或重新导入缺失文件。",
        )

    def _asset_load_issue(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        requirement: VisualRequirement,
        asset: Asset,
        exc: Exception,
    ) -> ReviewIssue:
        rule_code = rule_code_for_asset_load_error(exc)
        prefix = f"第 {slide.order + 1} 页素材「{asset.filename}」"
        required_note = "（必需素材）" if requirement.required else ""
        return self._issue(
            presentation_id,
            slide,
            layer=ReviewLayer.LAYOUT,
            category=ReviewCategory.VISUAL,
            severity=self._asset_failure_severity(requirement),
            rule_code=rule_code,
            title="素材文件无法读取",
            description=f"{prefix}：{exc}{required_note}",
            suggestion="确认文件路径有效、格式受支持且当前进程有读取权限。",
        )

    @staticmethod
    def _asset_failure_severity(requirement: VisualRequirement) -> ReviewSeverity:
        return ReviewSeverity.HIGH if requirement.required else ReviewSeverity.MEDIUM

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

        for check in report.checks:
            if check.passed or check.check_name == "drawing_classifier":
                continue
            if not self._check_applies_to_requirement(check.check_name, slide, requirement):
                continue
            spec = _CHECK_ISSUE_SPECS.get(check.check_name)
            if spec is None:
                continue
            rule_code, title, suggestion, layer, category, base_severity = spec
            decision = decide_check_issue(check, rule_code=rule_code)
            if not decision.emit:
                logger.debug(
                    "Suppressing low-confidence visual QA finding %s (confidence=%.2f)",
                    check.check_name,
                    check.confidence,
                )
                continue
            issues.append(
                self._issue(
                    presentation_id,
                    slide,
                    layer=layer,
                    category=category,
                    severity=base_severity,
                    rule_code=rule_code,
                    title=title,
                    description=f"{prefix}：{check.summary}",
                    suggestion=suggestion,
                    check=check,
                    requires_confirmation=decision.requires_confirmation,
                )
            )

        issues.extend(
            self._drawing_type_mismatch_issues(
                presentation_id,
                slide,
                requirement,
                asset,
                report,
                prefix=prefix,
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

    def _check_applies_to_requirement(
        self,
        check_name: str,
        slide: SlideSpec,
        requirement: VisualRequirement,
    ) -> bool:
        if check_name == "north_arrow":
            return requirement.type in {VisualType.SITE_PLAN, VisualType.MAP}
        if check_name == "legend_region":
            if requirement.type not in {VisualType.SITE_PLAN, VisualType.DIAGRAM, VisualType.MAP}:
                return False
            context = " ".join((slide.title, slide.message, requirement.description)).lower()
            return any(
                keyword in context
                for keyword in ("流线", "交通", "traffic", "circulation", "图例")
            )
        return True

    def _drawing_type_mismatch_issues(
        self,
        presentation_id: UUID,
        slide: SlideSpec,
        requirement: VisualRequirement,
        asset: Asset,
        report: VisualQAReport,
        *,
        prefix: str,
    ) -> list[ReviewIssue]:
        expected = _VISUAL_TYPE_TO_DRAWING.get(requirement.type)
        confidence = report.drawing_type_confidence or 0.0
        if (
            expected is None
            or report.drawing_type is None
            or report.drawing_type == expected
            or confidence < DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE
        ):
            return []

        synthetic = VisualQACheck(
            check_name="drawing_type_mismatch",
            passed=False,
            confidence=confidence,
            summary=(
                f"页面要求 {requirement.type.value}，"
                f"图像分类倾向 {report.drawing_type}"
            ),
            method="drawing_classifier",
            threshold=DRAWING_TYPE_MISMATCH_MIN_CONFIDENCE,
        )
        decision = decide_check_issue(
            synthetic,
            rule_code=ReviewRuleCode.VISUAL_DRAWING_TYPE_MISMATCH,
        )
        if not decision.emit:
            return []

        classifier = report.check("drawing_classifier")
        return [
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
                    f"图像分类倾向 {report.drawing_type}（置信度 {confidence:.2f}）。"
                ),
                suggestion="确认是否绑定了错误图纸，或在 Asset Board 中更换素材。",
                evidence=classifier.evidence if classifier else {},
                check=synthetic,
                requires_confirmation=decision.requires_confirmation,
            )
        ]

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
        check: VisualQACheck | None = None,
        confidence: float | None = None,
        detection_method: str | None = None,
        requires_confirmation: bool = False,
    ) -> ReviewIssue:
        resolved_evidence = evidence or (check.evidence if check else None)
        if resolved_evidence:
            description = f"{description}（依据：{self._format_evidence(resolved_evidence)}）"

        resolved_confidence = confidence if confidence is not None else (check.confidence if check else None)
        resolved_method = detection_method or (check.method if check else None)
        meta_parts: list[str] = []
        if resolved_confidence is not None:
            meta_parts.append(f"confidence={resolved_confidence:.2f}")
        if resolved_method:
            meta_parts.append(f"method={resolved_method}")
        if check is not None and check.threshold is not None:
            meta_parts.append(f"threshold={check.threshold}")
        if meta_parts:
            description = f"{description}（{'；'.join(meta_parts)}）"

        display_title = f"【疑似】{title}" if requires_confirmation else title
        resolved_severity = (
            ReviewSeverity.SUGGESTION if requires_confirmation else severity
        )

        return ReviewIssue(
            presentation_id=presentation_id,
            slide_id=slide.id,
            reviewer_layer=layer,
            category=category,
            severity=resolved_severity,
            rule_code=rule_code,
            title=display_title,
            description=description,
            suggestion=suggestion,
            confidence=resolved_confidence,
            detection_method=resolved_method,
            requires_confirmation=requires_confirmation,
        )

    @staticmethod
    def _format_evidence(evidence: dict[str, object]) -> str:
        parts: list[str] = []
        for key, value in evidence.items():
            if key in {"dominant_colors", "scores", "margin_contrast_by_edge"}:
                continue
            parts.append(f"{key}={value}")
        return "；".join(parts[:4])
