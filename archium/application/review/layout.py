"""Layout layer review — text density, asset resolution, Visual QA."""

from __future__ import annotations

from uuid import UUID

from archium.application.chunk_models import ProjectContextBundle
from archium.application.review.base import SKIPPABLE_SLIDE_TYPES, ReviewRunnerBase
from archium.application.review.llm_helpers import run_llm_multi_layer_review
from archium.application.visual_qa_service import VisualQAService
from archium.domain.asset import Asset
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, VisualType
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec
from archium.logging import get_logger

logger = get_logger(__name__, operation="automated_review")

_TEXT_DENSITY_THRESHOLD = 280
_LONG_BULLET_THRESHOLD = 40
_EXTREME_ASPECT_RATIO_LOW = 0.4
_EXTREME_ASPECT_RATIO_HIGH = 2.5


def _estimate_text_load(slide: SlideSpec) -> int:
    load = len(slide.message.strip())
    load += sum(len(point.strip()) for point in slide.key_points)
    load += len(slide.title.strip()) // 2
    return load


class LayoutReviewer(ReviewRunnerBase):
    """Check text density, visual readiness, asset resolution, and Visual QA."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        assets_by_id = {}
        if project_id is not None:
            assets_by_id = {
                asset.id: asset for asset in self._assets.list_by_project(project_id)
            }

        issues: list[ReviewIssue] = []

        for slide in slides:
            text_load = _estimate_text_load(slide)
            if (
                slide.slide_type not in SKIPPABLE_SLIDE_TYPES
                and text_load > _TEXT_DENSITY_THRESHOLD
            ):
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.LAYOUT,
                        category=ReviewCategory.LENGTH,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
                        title="页面信息密度过高",
                        description=(
                            f"第 {slide.order + 1} 页文本量估算为 {text_load} 字当量，"
                            "超过建议上限，可能导致版面溢出。"
                        ),
                        suggestion="减少要点数量或缩短每条表述。",
                    )
                )
            for point in slide.key_points:
                if len(point.strip()) > _LONG_BULLET_THRESHOLD:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.LAYOUT,
                            category=ReviewCategory.LENGTH,
                            severity=ReviewSeverity.SUGGESTION,
                            rule_code=ReviewRuleCode.LAYOUT_BULLET_TOO_LONG,
                            title="单条要点过长",
                            description=(
                                f"第 {slide.order + 1} 页存在超过 {_LONG_BULLET_THRESHOLD} 字的要点，"
                                "换行后可能超出文本框。"
                            ),
                            suggestion="拆分为两条要点或使用更短表述。",
                        )
                    )
                    break

            if len(slide.key_points) > 5:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.LAYOUT,
                        category=ReviewCategory.LENGTH,
                        severity=ReviewSeverity.SUGGESTION,
                        rule_code=ReviewRuleCode.LAYOUT_TOO_MANY_BULLETS,
                        title="要点过多",
                        description=f"第 {slide.order + 1} 页要点超过 5 条，建议精简。",
                    )
                )
            if (
                slide.message.strip()
                and slide.slide_type not in SKIPPABLE_SLIDE_TYPES
                and len(slide.message.strip()) > 120
            ):
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.LAYOUT,
                        category=ReviewCategory.LENGTH,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.LAYOUT_MESSAGE_TOO_LONG,
                        title="核心结论过长",
                        description=(
                            f"第 {slide.order + 1} 页核心结论超过 120 字，"
                            "可能导致版面拥挤或溢出。"
                        ),
                        suggestion="拆分为要点列表或精简表述。",
                    )
                )

            for requirement in slide.visual_requirements:
                if requirement.type == VisualType.TEXT_ONLY:
                    continue
                if requirement.required and not requirement.preferred_asset_ids:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.LAYOUT,
                            category=ReviewCategory.VISUAL,
                            severity=ReviewSeverity.MEDIUM,
                            rule_code=ReviewRuleCode.LAYOUT_MISSING_ASSET,
                            title="缺少匹配素材",
                            description=(
                                f"第 {slide.order + 1} 页需要 {requirement.type.value} 类视觉，"
                                "但未匹配到项目素材。"
                            ),
                            suggestion="上传图纸/照片或在 Asset Board 中手动指定素材。",
                        )
                    )
                asset_id = requirement.primary_asset_id
                if asset_id is not None:
                    asset = assets_by_id.get(asset_id)
                    if asset is not None and asset.is_low_resolution:
                        issues.append(
                            self._issue(
                                presentation_id,
                                slide,
                                layer=ReviewLayer.LAYOUT,
                                category=ReviewCategory.VISUAL,
                                severity=ReviewSeverity.MEDIUM,
                                rule_code=ReviewRuleCode.LAYOUT_LOW_RESOLUTION_ASSET,
                                title="素材分辨率偏低",
                                description=(
                                    f"第 {slide.order + 1} 页素材「{asset.filename}」"
                                    f"分辨率为 {asset.width}×{asset.height}，"
                                    "投影或打印时可能模糊。"
                                ),
                                suggestion="替换更高分辨率素材或裁剪重点区域。",
                            )
                        )
                    if asset is not None:
                        ratio = asset.aspect_ratio
                        if ratio is not None and (
                            ratio < _EXTREME_ASPECT_RATIO_LOW or ratio > _EXTREME_ASPECT_RATIO_HIGH
                        ):
                            issues.append(
                                self._issue(
                                    presentation_id,
                                    slide,
                                    layer=ReviewLayer.LAYOUT,
                                    category=ReviewCategory.VISUAL,
                                    severity=ReviewSeverity.SUGGESTION,
                                    rule_code=ReviewRuleCode.LAYOUT_EXTREME_ASPECT_RATIO,
                                    title="素材宽高比极端",
                                    description=(
                                        f"第 {slide.order + 1} 页素材「{asset.filename}」"
                                        f"宽高比为 {ratio:.2f}，"
                                        "直接填充版式时可能出现拉伸或留白。"
                                    ),
                                    suggestion="裁剪为标准比例或使用 Asset Board 标记需裁剪。",
                                )
                            )

        if self._llm_review_enabled() and self._llm is not None:
            issues.extend(
                run_llm_multi_layer_review(
                    self._llm,
                    self._settings,
                    presentation_id,
                    slides,
                    brief=brief,
                    storyline=storyline,
                    context_bundle=context_bundle,
                )
            )

        if project_id is not None and self._settings.visual_qa_enabled:
            issues.extend(self._run_visual_qa_review(presentation_id, slides, assets_by_id))

        return self._persist(presentation_id, issues)

    def _run_visual_qa_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        assets_by_id: dict[UUID, Asset],
    ) -> list[ReviewIssue]:
        try:
            return VisualQAService(self._session).review_slides(
                presentation_id,
                slides,
                assets_by_id,
            )
        except RuntimeError as exc:
            logger.warning("Visual QA disabled: %s", exc)
            return []
        except Exception as exc:
            logger.warning("Visual QA failed: %s", exc)
            return []
