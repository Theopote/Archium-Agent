"""Automated four-layer presentation review (content / evidence / architectural / layout)."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.config.settings import Settings, get_settings
from archium.domain.enums import (
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
    SlideType,
    VisualType,
)
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import AssetRepository, ReviewRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import ProfessionalReviewDraft
from archium.logging import get_logger
from archium.prompts.professional_review import (
    PROFESSIONAL_REVIEW_SYSTEM_PROMPT,
    build_professional_review_user_prompt,
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


def critical_export_block_messages(
    issues: list[ReviewIssue],
    *,
    block_enabled: bool,
) -> list[str]:
    """Return workflow error messages when critical open issues should block export."""
    if not block_enabled:
        return []
    return [
        f"[{issue.category.value}] {issue.title}: {issue.description}"
        for issue in issues
        if issue.severity == ReviewSeverity.CRITICAL and issue.status == ReviewStatus.OPEN
    ]


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
                        title="标题重复",
                        description=f"标题「{title}」在 {count} 页中重复出现，建议区分章节重点。",
                    )
                )

        if brief is not None and brief.core_message.strip() and slides:
            tokens = [
                token
                for token in re.split(r"[\s，,、；;。.]+", brief.core_message.strip())
                if len(token) >= 2
            ]
            combined = " ".join(slide.message for slide in slides)
            if tokens and not any(token in combined for token in tokens[:5]):
                issues.append(
                    ReviewIssue(
                        presentation_id=presentation_id,
                        reviewer_layer=ReviewLayer.CONTENT,
                        category=ReviewCategory.COVERAGE,
                        severity=ReviewSeverity.MEDIUM,
                        title="Brief 核心信息未体现",
                        description=(
                            f"Brief 核心信息「{brief.core_message}」"
                            "未在 Slide 结论中找到明显呼应。"
                        ),
                        suggestion="调整各页结论，确保与 Brief 核心信息一致。",
                    )
                )

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
                            title="视觉证据未确认",
                            description=(
                                f"第 {slide.order + 1} 页已匹配 {requirement.type.value} 素材，"
                                "但尚未人工确认是否支持该页结论。"
                            ),
                            suggestion="在 Asset Board 中确认素材与结论的对应关系。",
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
                    title="面积单位表述不一致",
                    description=f"汇报中混用了多种面积单位：{', '.join(sorted(unit_styles))}。",
                    suggestion="统一使用 ㎡ 或 平方米 等单一单位体系。",
                )
            )

        for slide in slides:
            for requirement in slide.visual_requirements:
                if requirement.type == VisualType.SITE_PLAN:
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
                                title="平面图缺少楼层标注提示",
                                description=(
                                    f"第 {slide.order + 1} 页使用平面图，"
                                    "建议标注楼层或标高信息。"
                                ),
                            )
                        )

        if self._settings.llm_professional_review_enabled and self._settings.llm_configured:
            if self._llm is not None:
                issues.extend(
                    self._run_llm_professional_review(
                        presentation_id,
                        slides,
                        brief=brief,
                        storyline=storyline,
                    )
                )
            else:
                logger.warning("LLM professional review enabled but no provider was injected")

        return self._persist(presentation_id, issues)

    def run_layout_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
    ) -> list[ReviewIssue]:
        """Check text density, visual readiness, and asset resolution."""
        assets_by_id = {}
        if project_id is not None:
            assets_by_id = {
                asset.id: asset for asset in self._assets.list_by_project(project_id)
            }

        issues: list[ReviewIssue] = []

        for slide in slides:
            if len(slide.key_points) > 5:
                issues.append(
                    self._issue(
                        presentation_id,
                        slide,
                        layer=ReviewLayer.LAYOUT,
                        category=ReviewCategory.LENGTH,
                        severity=ReviewSeverity.SUGGESTION,
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
                                title="素材分辨率偏低",
                                description=(
                                    f"第 {slide.order + 1} 页素材「{asset.filename}」"
                                    f"分辨率为 {asset.width}×{asset.height}，"
                                    "投影或打印时可能模糊。"
                                ),
                                suggestion="替换更高分辨率素材或裁剪重点区域。",
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
            self.run_layout_review(presentation_id, slides, project_id=project_id)
        )
        return issues

    def summarize_for_slides(self, issues: list[ReviewIssue]) -> list[str]:
        return [f"{issue.title}: {issue.description}" for issue in issues if issue.slide_id]

    def _run_llm_professional_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None,
        storyline: Storyline | None,
    ) -> list[ReviewIssue]:
        assert self._llm is not None
        brief_summary = (
            f"标题: {brief.title}\n核心信息: {brief.core_message}\n"
            f"必要章节: {', '.join(brief.required_sections)}"
            if brief is not None
            else "无 Brief"
        )
        storyline_summary = (
            f"论点: {storyline.thesis}\n章节: "
            + ", ".join(chapter.title for chapter in storyline.chapters)
            if storyline is not None
            else "无 Storyline"
        )
        slides_summary = "\n".join(
            f"p{slide.order + 1} [{slide.slide_type.value}] {slide.title}: {slide.message}"
            for slide in sorted(slides, key=lambda item: item.order)
        )
        request = LLMRequest(
            system_prompt=PROFESSIONAL_REVIEW_SYSTEM_PROMPT,
            user_prompt=build_professional_review_user_prompt(
                brief_summary=brief_summary,
                storyline_summary=storyline_summary,
                slides_summary=slides_summary,
            ),
            model=self._settings.llm_model,
            temperature=0.2,
            json_mode=True,
        )
        try:
            draft = self._llm.generate_structured(request, ProfessionalReviewDraft)
        except Exception as exc:
            logger.warning("LLM professional review failed: %s", exc)
            return []

        slides_by_order = {slide.order: slide for slide in slides}
        issues: list[ReviewIssue] = []
        for item in draft.issues:
            slide = slides_by_order.get(item.slide_order) if item.slide_order is not None else None
            issues.append(
                ReviewIssue(
                    presentation_id=presentation_id,
                    slide_id=slide.id if slide is not None else None,
                    reviewer_layer=ReviewLayer.ARCHITECTURAL,
                    category=_parse_review_category(item.category),
                    severity=_parse_review_severity(item.severity),
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
        title: str,
        description: str,
        suggestion: str | None = None,
    ) -> ReviewIssue:
        return ReviewIssue(
            presentation_id=presentation_id,
            slide_id=slide.id,
            reviewer_layer=layer,
            category=category,
            severity=severity,
            title=title,
            description=description,
            suggestion=suggestion,
        )


def _detect_area_unit_styles(slides: list[SlideSpec]) -> set[str]:
    styles: set[str] = set()
    combined = " ".join(
        slide.message + " " + " ".join(slide.key_points) for slide in slides
    )
    for style_name, pattern in _AREA_UNIT_PATTERNS:
        if pattern.search(combined):
            styles.add(style_name)
    return styles


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
