"""Architectural layer review — structure, coverage, drawing conventions."""

from __future__ import annotations

import re
from uuid import UUID

from archium.application.review.base import ReviewRunnerBase
from archium.domain.enums import (
    PresentationType,
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    VisualType,
)
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.domain.slide import SlideSpec

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


def _detect_area_unit_styles(slides: list[SlideSpec]) -> set[str]:
    styles: set[str] = set()
    combined = " ".join(
        slide.message + " " + " ".join(slide.key_points) for slide in slides
    )
    for style_name, pattern in _AREA_UNIT_PATTERNS:
        if pattern.search(combined):
            styles.add(style_name)
    return styles


class ArchitecturalReviewer(ReviewRunnerBase):
    """Check structure, coverage, and architectural drawing conventions."""

    def run(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
    ) -> list[ReviewIssue]:
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
