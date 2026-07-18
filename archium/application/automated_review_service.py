"""Automated four-layer presentation review (content / evidence / architectural / layout)."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.application.visual_qa_service import VisualQAService, asset_load_rule_codes
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import (
    PresentationType,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    SlideType,
    VisualType,
)
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode, is_auto_fixable_rule
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import AssetRepository, ReviewRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import (
    BriefAlignmentDraft,
    ProfessionalReviewDraft,
    ReviewIssueDraft,
)
from archium.logging import get_logger
from archium.prompts.brief_alignment import (
    BRIEF_ALIGNMENT_SYSTEM_PROMPT,
    build_brief_alignment_user_prompt,
)
from archium.prompts.layer_review import (
    LAYER_REVIEW_SYSTEM_PROMPT,
    build_layer_review_user_prompt,
)

logger = get_logger(__name__, operation="automated_review")

_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_SKIPPABLE_SLIDE_TYPES = {SlideType.TITLE, SlideType.SECTION, SlideType.CLOSING}
_NORTH_ARROW_HINTS = ("指北针", "北向", "north", "compass")
_FLOOR_LABEL_HINTS = ("层", "floor", "f1", "f2", "f3", "首层", "地下")
_AREA_UNIT_PATTERNS = (
    ("sqm_symbol", re.compile(r"㎡")),
    ("sqm_ascii", re.compile(r"\bm2\b", re.IGNORECASE)),
    ("sqm_cn", re.compile(r"平方米")),
)
_FLOW_TRAFFIC_KEYWORDS = ("流线", "交通", "circulation", "traffic", "车行", "人行")
_FLOW_COLOR_HINTS = ("色", "颜色", "图例", "legend", "红线", "蓝线", "绿线", "color")
_CONSTRUCTION_DETAIL_KEYWORDS = (
    "配筋",
    "构造大样",
    "施工图",
    "结构柱",
    "梁配筋",
    "节点详图",
    "大样图",
    "幕墙节点",
)
_CONCEPT_PRESENTATION_TYPES = {
    PresentationType.CONCEPT,
    PresentationType.CLIENT_REVIEW,
    PresentationType.SCHEMATIC,
    PresentationType.COMPETITION,
    PresentationType.INTERNAL,
}
_TEXT_DENSITY_THRESHOLD = 280
_LONG_BULLET_THRESHOLD = 40
_EXTREME_ASPECT_RATIO_LOW = 0.4
_EXTREME_ASPECT_RATIO_HIGH = 2.5


def critical_export_block_messages(
    issues: list[ReviewIssue],
    *,
    block_enabled: bool,
) -> list[str]:
    """Return workflow error messages when open review issues should block export."""
    if not block_enabled:
        return []
    asset_load_rules = asset_load_rule_codes()
    messages: list[str] = []
    for issue in issues:
        if issue.status != ReviewStatus.OPEN:
            continue
        if issue.severity == ReviewSeverity.CRITICAL:
            messages.append(f"[{issue.category.value}] {issue.title}: {issue.description}")
            continue
        if (
            issue.severity == ReviewSeverity.HIGH
            and issue.rule_code in asset_load_rules
        ):
            messages.append(f"[{issue.category.value}] {issue.title}: {issue.description}")
    return messages


class AutomatedReviewService:
    """Run rule-based and optional LLM-assisted presentation QA checks."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._reviews = ReviewRepository(session)
        self._assets = AssetRepository(session)
        self._llm = llm
        self._settings = settings or get_settings()

    def run_content_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
    ) -> list[ReviewIssue]:
        """Check slide copy clarity, repetition, and Brief alignment."""
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
            if not slide.message.strip() and slide.slide_type not in _SKIPPABLE_SLIDE_TYPES:
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
                and slide.slide_type not in _SKIPPABLE_SLIDE_TYPES
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

    def run_evidence_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        """Check citations, numeric claims, and claim-to-evidence alignment."""
        has_sources = context_bundle is not None and bool(context_bundle.chunks)
        issues: list[ReviewIssue] = []

        for slide in slides:
            if slide.slide_type in _SKIPPABLE_SLIDE_TYPES:
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

    def run_architectural_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
    ) -> list[ReviewIssue]:
        """Check structure, coverage, and architectural drawing conventions."""
        issues: list[ReviewIssue] = []

        if brief is not None and slides:
            target = brief.target_slide_count
            actual = len(slides)
            if target > 0 and abs(actual - target) / target > 0.25:
                issues.append(
                    ReviewIssue(
                        presentation_id=presentation_id,
                        reviewer_layer=ReviewLayer.ARCHITECTURAL,
                        category=ReviewCategory.STRUCTURE,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.ARCH_SLIDE_COUNT_DEVIATION,
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
                                reviewer_layer=ReviewLayer.ARCHITECTURAL,
                                category=ReviewCategory.COVERAGE,
                                severity=ReviewSeverity.CRITICAL,
                                rule_code=ReviewRuleCode.ARCH_REQUIRED_SECTION_MISSING,
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
                        reviewer_layer=ReviewLayer.ARCHITECTURAL,
                        category=ReviewCategory.STRUCTURE,
                        severity=ReviewSeverity.MEDIUM,
                        rule_code=ReviewRuleCode.ARCH_CHAPTER_WITHOUT_SLIDES,
                        title="章节缺少对应页面",
                        description=f"Storyline 章节 {chapter_id} 未分配任何 Slide。",
                    )
                )

        unit_styles = _detect_area_unit_styles(slides)
        if len(unit_styles) > 1:
            issues.append(
                ReviewIssue(
                    presentation_id=presentation_id,
                    reviewer_layer=ReviewLayer.ARCHITECTURAL,
                    category=ReviewCategory.CONSISTENCY,
                    severity=ReviewSeverity.MEDIUM,
                    rule_code=ReviewRuleCode.ARCH_INCONSISTENT_AREA_UNITS,
                    title="面积单位表述不一致",
                    description=f"汇报中混用了多种面积单位：{', '.join(sorted(unit_styles))}。",
                    suggestion="统一使用 ㎡ 或 平方米 等单一单位体系。",
                )
            )

        for slide in slides:
            if brief is not None and brief.presentation_type in _CONCEPT_PRESENTATION_TYPES:
                combined = " ".join([slide.title, slide.message, *slide.key_points])
                for keyword in _CONSTRUCTION_DETAIL_KEYWORDS:
                    if keyword in combined:
                        issues.append(
                            self._issue(
                                presentation_id,
                                slide,
                                layer=ReviewLayer.ARCHITECTURAL,
                                category=ReviewCategory.CONSISTENCY,
                                severity=ReviewSeverity.MEDIUM,
                                rule_code=ReviewRuleCode.ARCH_CONCEPT_HAS_CONSTRUCTION_DETAIL,
                                title="概念汇报包含施工图级细节",
                                description=(
                                    f"第 {slide.order + 1} 页出现「{keyword}」，"
                                    f"与 {brief.presentation_type.value} 阶段精度可能不匹配。"
                                ),
                                suggestion="概念/方案汇报中建议聚焦策略与空间逻辑，施工图细节移至专篇。",
                            )
                        )
                        break

            for requirement in slide.visual_requirements:
                if requirement.type == VisualType.SITE_PLAN:
                    if requirement.bound_asset_ids() and self._settings.visual_qa_enabled:
                        continue
                    context = " ".join(
                        (
                            slide.title,
                            slide.message,
                            requirement.description,
                        )
                    ).lower()
                    if not any(hint in context for hint in _NORTH_ARROW_HINTS):
                        issues.append(
                            self._issue(
                                presentation_id,
                                slide,
                                layer=ReviewLayer.ARCHITECTURAL,
                                category=ReviewCategory.VISUAL,
                                severity=ReviewSeverity.SUGGESTION,
                                rule_code=ReviewRuleCode.ARCH_PLAN_MISSING_NORTH_ARROW,
                                title="总平面图缺少方位标注提示",
                                description=(
                                    f"第 {slide.order + 1} 页使用总平面图，"
                                    "建议在说明或素材中标注指北针/北向。"
                                ),
                            )
                        )
                if requirement.type == VisualType.FLOOR_PLAN:
                    context = " ".join(
                        (
                            slide.title,
                            slide.message,
                            requirement.description,
                        )
                    ).lower()
                    if not any(hint in context for hint in _FLOOR_LABEL_HINTS):
                        issues.append(
                            self._issue(
                                presentation_id,
                                slide,
                                layer=ReviewLayer.ARCHITECTURAL,
                                category=ReviewCategory.VISUAL,
                                severity=ReviewSeverity.SUGGESTION,
                                rule_code=ReviewRuleCode.ARCH_PLAN_MISSING_FLOOR_LABEL,
                                title="平面图缺少楼层标注提示",
                                description=(
                                    f"第 {slide.order + 1} 页使用平面图，"
                                    "建议标注楼层或标高信息。"
                                ),
                            )
                        )
                if requirement.type in {VisualType.SITE_PLAN, VisualType.DIAGRAM, VisualType.MAP}:
                    if requirement.bound_asset_ids() and self._settings.visual_qa_enabled:
                        continue
                    context = " ".join(
                        (
                            slide.title,
                            slide.message,
                            requirement.description,
                        )
                    ).lower()
                    if any(keyword in context for keyword in _FLOW_TRAFFIC_KEYWORDS) and not any(
                        hint in context for hint in _FLOW_COLOR_HINTS
                    ):
                        issues.append(
                            self._issue(
                                presentation_id,
                                slide,
                                layer=ReviewLayer.ARCHITECTURAL,
                                category=ReviewCategory.VISUAL,
                                severity=ReviewSeverity.SUGGESTION,
                                rule_code=ReviewRuleCode.ARCH_FLOW_DIAGRAM_MISSING_LEGEND,
                                title="交通流线图缺少颜色图例提示",
                                description=(
                                    f"第 {slide.order + 1} 页涉及交通/流线表述，"
                                    "建议在图面或说明中标注流线颜色图例。"
                                ),
                            )
                        )

        return self._persist(presentation_id, issues)

    def run_layout_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        """Check text density, visual readiness, and asset resolution."""
        assets_by_id = {}
        if project_id is not None:
            assets_by_id = {
                asset.id: asset for asset in self._assets.list_by_project(project_id)
            }

        issues: list[ReviewIssue] = []

        for slide in slides:
            text_load = _estimate_text_load(slide)
            if (
                slide.slide_type not in _SKIPPABLE_SLIDE_TYPES
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
                and slide.slide_type not in _SKIPPABLE_SLIDE_TYPES
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

        if self._llm_review_enabled():
            issues.extend(
                self._run_llm_multi_layer_review(
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

    def run_professional_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
        project_id: UUID | None = None,
    ) -> list[ReviewIssue]:
        """Run all four review layers (backward-compatible aggregate entry point)."""
        issues: list[ReviewIssue] = []
        issues.extend(self.run_content_review(presentation_id, slides, brief=brief))
        issues.extend(
            self.run_evidence_review(presentation_id, slides, context_bundle=context_bundle)
        )
        issues.extend(
            self.run_architectural_review(
                presentation_id,
                slides,
                brief=brief,
                storyline=storyline,
            )
        )
        issues.extend(
            self.run_layout_review(
                presentation_id,
                slides,
                project_id=project_id,
                brief=brief,
                storyline=storyline,
                context_bundle=context_bundle,
            )
        )
        return issues

    def summarize_for_slides(self, issues: list[ReviewIssue]) -> list[str]:
        return [f"{issue.title}: {issue.description}" for issue in issues if issue.slide_id]

    def _llm_review_enabled(self) -> bool:
        return (
            self._settings.llm_professional_review_enabled
            and self._settings.llm_configured
            and self._llm is not None
        )

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

    def _check_brief_alignment(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        brief: PresentationBrief,
    ) -> ReviewIssue | None:
        if self._llm_review_enabled():
            llm_issue, llm_succeeded = self._run_llm_brief_alignment(
                presentation_id, brief, slides
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

    def _run_llm_brief_alignment(
        self,
        presentation_id: UUID,
        brief: PresentationBrief,
        slides: list[SlideSpec],
    ) -> tuple[ReviewIssue | None, bool]:
        assert self._llm is not None
        brief_summary = _format_brief_summary(brief)
        slides_summary = _format_slides_summary(slides)
        request = LLMRequest(
            system_prompt=BRIEF_ALIGNMENT_SYSTEM_PROMPT,
            user_prompt=build_brief_alignment_user_prompt(
                brief_summary=brief_summary,
                slides_summary=slides_summary,
            ),
            model=self._settings.llm_model,
            temperature=0.1,
            json_mode=True,
        )
        try:
            draft = self._llm.generate_structured(request, BriefAlignmentDraft)
        except Exception as exc:
            logger.warning("LLM Brief alignment check failed: %s", exc)
            return None, False

        if draft.aligned:
            return None, True

        gap = draft.gap_summary.strip() or "Slide 结论与 Brief 核心诉求存在语义偏差。"
        severity = (
            ReviewSeverity.HIGH
            if draft.confidence >= 0.75
            else ReviewSeverity.MEDIUM
        )
        return (
            ReviewIssue(
                presentation_id=presentation_id,
                reviewer_layer=ReviewLayer.CONTENT,
                category=ReviewCategory.COVERAGE,
                severity=severity,
                rule_code=ReviewRuleCode.CONTENT_BRIEF_ALIGNMENT_GAP,
                title="Brief 语义对齐不足",
                description=gap,
                suggestion=draft.suggestion or "调整各页结论，确保与 Brief 核心信息一致。",
            ),
            True,
        )

    def _run_llm_multi_layer_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None,
        storyline: Storyline | None,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        assert self._llm is not None
        brief_summary = _format_brief_summary(brief) if brief is not None else "无 Brief"
        storyline_summary = (
            _format_storyline_summary(storyline) if storyline is not None else "无 Storyline"
        )
        context_summary = _format_context_summary(context_bundle)
        slides_summary = _format_slides_summary(slides, include_key_points=True)
        request = LLMRequest(
            system_prompt=LAYER_REVIEW_SYSTEM_PROMPT,
            user_prompt=build_layer_review_user_prompt(
                brief_summary=brief_summary,
                storyline_summary=storyline_summary,
                slides_summary=slides_summary,
                context_summary=context_summary,
            ),
            model=self._settings.llm_model,
            temperature=0.2,
            json_mode=True,
        )
        try:
            draft = self._llm.generate_structured(request, ProfessionalReviewDraft)
        except Exception as exc:
            logger.warning("LLM multi-layer review failed: %s", exc)
            return []

        slides_by_order = {slide.order: slide for slide in slides}
        issues: list[ReviewIssue] = []
        for item in draft.issues:
            slide = slides_by_order.get(item.slide_order) if item.slide_order is not None else None
            issues.append(
                ReviewIssue(
                    presentation_id=presentation_id,
                    slide_id=slide.id if slide is not None else None,
                    reviewer_layer=_parse_review_layer(item.reviewer_layer),
                    category=_parse_review_category(item.category),
                    severity=_parse_review_severity(item.severity),
                    rule_code=_llm_rule_code(item),
                    title=item.title.strip(),
                    description=item.description.strip(),
                    suggestion=item.suggestion.strip() if item.suggestion else None,
                )
            )
        return issues

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
        layer: ReviewLayer,
        category: ReviewCategory,
        severity: ReviewSeverity,
        rule_code: str,
        title: str,
        description: str,
        suggestion: str | None = None,
        auto_fixable: bool | None = None,
    ) -> ReviewIssue:
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
            auto_fixable=is_auto_fixable_rule(rule_code) if auto_fixable is None else auto_fixable,
        )


def _llm_rule_code(item: ReviewIssueDraft) -> str:
    raw = (item.rule_code or "").strip()
    if raw:
        return raw.upper()
    layer = item.reviewer_layer.strip().upper() or "UNKNOWN"
    category = item.category.strip().upper() or "OTHER"
    return f"LLM.{layer}.{category}"


def _detect_area_unit_styles(slides: list[SlideSpec]) -> set[str]:
    styles: set[str] = set()
    combined = " ".join(
        slide.message + " " + " ".join(slide.key_points) for slide in slides
    )
    for style_name, pattern in _AREA_UNIT_PATTERNS:
        if pattern.search(combined):
            styles.add(style_name)
    return styles


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


def _estimate_text_load(slide: SlideSpec) -> int:
    load = len(slide.message.strip())
    load += sum(len(point.strip()) for point in slide.key_points)
    load += len(slide.title.strip()) // 2
    return load


def _parse_review_layer(value: str) -> ReviewLayer:
    try:
        return ReviewLayer(value.strip().lower())
    except ValueError:
        return ReviewLayer.ARCHITECTURAL


def _parse_review_category(value: str) -> ReviewCategory:
    try:
        return ReviewCategory(value.strip().lower())
    except ValueError:
        return ReviewCategory.OTHER


def _parse_review_severity(value: str) -> ReviewSeverity:
    try:
        return ReviewSeverity(value.strip().lower())
    except ValueError:
        return ReviewSeverity.SUGGESTION


def _format_brief_summary(brief: PresentationBrief) -> str:
    sections = ", ".join(brief.required_sections) or "无"
    decisions = ", ".join(brief.decisions_required) or "无"
    return (
        f"标题: {brief.title}\n"
        f"核心信息: {brief.core_message}\n"
        f"必要章节: {sections}\n"
        f"需决策事项: {decisions}\n"
        f"受众: {brief.audience}\n"
        f"目的: {brief.purpose}"
    )


def _format_storyline_summary(storyline: Storyline) -> str:
    chapters = ", ".join(
        f"{chapter.id}:{chapter.title}({chapter.key_message})"
        for chapter in storyline.chapters
    )
    return f"论点: {storyline.thesis}\n章节: {chapters}"


def _format_context_summary(context_bundle: ProjectContextBundle | None) -> str:
    if context_bundle is None or not context_bundle.chunks:
        return "无项目资料片段"
    lines = []
    for chunk in context_bundle.chunks[:8]:
        label = chunk.section_title or f"chunk-{chunk.chunk_index}"
        preview = chunk.content.strip().replace("\n", " ")[:120]
        lines.append(f"- [{label}] {preview}")
    return "\n".join(lines)


def _format_slides_summary(slides: list[SlideSpec], *, include_key_points: bool = False) -> str:
    lines: list[str] = []
    for slide in sorted(slides, key=lambda item: item.order):
        line = f"p{slide.order + 1} [{slide.slide_type.value}] {slide.title}: {slide.message}"
        if include_key_points and slide.key_points:
            line += " | 要点: " + "; ".join(slide.key_points[:5])
        if slide.source_citations:
            line += f" | 引用: {len(slide.source_citations)}"
        if slide.visual_requirements:
            visuals = ", ".join(req.type.value for req in slide.visual_requirements)
            line += f" | 视觉: {visuals}"
        lines.append(line)
    return "\n".join(lines)
