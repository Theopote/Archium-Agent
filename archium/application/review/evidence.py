"""Evidence layer review — citations, numeric claims, visual evidence."""

from __future__ import annotations

import re
from uuid import UUID

from archium.application.chunk_models import ProjectContextBundle
from archium.application.review.base import SKIPPABLE_SLIDE_TYPES, ReviewRunnerBase
from archium.domain.enums import ReviewCategory, ReviewLayer, ReviewSeverity, VisualType
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def _tokenize_text(text: str) -> set[str]:
    return {
        token.strip().lower()
        for token in re.split(r"[\s，,、；;。.]+", text)
        if len(token.strip()) >= 2
    }


def _visual_supports_message(message: str, description: str) -> bool:
    message_tokens = _tokenize_text(message)
    description_tokens = _tokenize_text(description)
    if not message_tokens or not description_tokens:
        return True
    return bool(message_tokens & description_tokens)


class EvidenceReviewer(ReviewRunnerBase):
    """Check citations, numeric claims, and claim-to-evidence alignment."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        has_sources = context_bundle is not None and bool(context_bundle.chunks)
        issues: list[ReviewIssue] = []

        for slide in slides:
            if slide.slide_type in SKIPPABLE_SLIDE_TYPES:
                continue

            if has_sources and not slide.source_citations:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.EVIDENCE,
                        category=ReviewCategory.CITATION,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.EVIDENCE_MISSING_CITATION,
                        title="缺少引用来源",
                        description=f"第 {slide.order + 1} 页「{slide.title}」未关联项目资料。",
                        suggestion="补充 chunk 引用或上传对应图纸/照片。",
                    )
                )

            if _NUMBER_PATTERN.search(slide.message) and not slide.source_citations:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.EVIDENCE,
                        category=ReviewCategory.CITATION,
                        severity=ReviewSeverity.HIGH,
                        rule_code=ReviewRuleCode.EVIDENCE_NUMERIC_CLAIM_UNCITED,
                        title="数值结论缺少依据",
                        description=(
                            f"第 {slide.order + 1} 页「{slide.title}」包含数值表述但未标注来源。"
                        ),
                        suggestion="补充数据出处或标注为示意/估算。",
                    )
                )

            for requirement in slide.visual_requirements:
                if requirement.type == VisualType.TEXT_ONLY or not requirement.required:
                    continue
                if requirement.preferred_asset_ids and not requirement.confirmed:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.EVIDENCE,
                            category=ReviewCategory.VISUAL,
                            severity=ReviewSeverity.MEDIUM,
                            rule_code=ReviewRuleCode.EVIDENCE_VISUAL_EVIDENCE_UNCONFIRMED,
                            title="视觉证据未确认",
                            description=(
                                f"第 {slide.order + 1} 页已匹配 {requirement.type.value} 素材，"
                                "但尚未人工确认是否支持该页结论。"
                            ),
                            suggestion="在 Asset Board 中确认素材与结论的对应关系。",
                        )
                    )
                elif requirement.required and not requirement.preferred_asset_ids:
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.EVIDENCE,
                            category=ReviewCategory.VISUAL,
                            severity=ReviewSeverity.HIGH,
                            rule_code=ReviewRuleCode.EVIDENCE_MISSING_VISUAL_EVIDENCE,
                            title="结论缺少视觉证据",
                            description=(
                                f"第 {slide.order + 1} 页「{slide.title}」需要 {requirement.type.value} "
                                "类视觉支撑，但未匹配到项目素材。"
                            ),
                            suggestion="上传对应图纸/照片，或在 Asset Board 中指定素材。",
                        )
                    )
                elif requirement.required and not _visual_supports_message(
                    slide.message,
                    requirement.description,
                ):
                    issues.append(
                        self._issue(
                            presentation_id,
                            slide,
                            layer=ReviewLayer.EVIDENCE,
                            category=ReviewCategory.CONSISTENCY,
                            severity=ReviewSeverity.MEDIUM,
                            rule_code=ReviewRuleCode.EVIDENCE_WEAK_VISUAL_ALIGNMENT,
                            title="视觉素材与结论关联性弱",
                            description=(
                                f"第 {slide.order + 1} 页结论与 {requirement.type.value} "
                                f"素材说明「{requirement.description}」缺少明显关键词呼应。"
                            ),
                            suggestion="调整素材说明或结论表述，确保图文相互支撑。",
                        )
                    )

        return self._persist(presentation_id, issues)
