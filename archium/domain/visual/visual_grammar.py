"""Architectural Visual Grammar — page archetypes and composition recipes (VG-001).

Maps building-report page *kinds* (区位分析、现状问题、设计策略、改造前后) to
visual strategy: reading order, layout-family preference, variant hints, and tone.
Does **not** emit coordinates — geometry remains with LayoutFamily generators.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from archium.domain.enums import SlideType, VisualType
from archium.domain.visual.enums import (
    ContinuityRole,
    DensityLevel,
    LayoutFamily,
    VisualContentType,
)


class PageArchetype(StrEnum):
    """Architectural report page archetype — semantic visual page kind."""

    SITE_CONTEXT_ANALYSIS = "site_context_analysis"
    SITE_PROBLEM_DIAGNOSIS = "site_problem_diagnosis"
    DESIGN_STRATEGY = "design_strategy"
    BEFORE_AFTER_TRANSFORMATION = "before_after_transformation"
    GENERIC = "generic"


@dataclass(frozen=True)
class ArchetypeSignal:
    """Weighted text/visual signal for archetype recognition."""

    pattern: re.Pattern[str]
    weight: float = 1.0
    label: str = ""


@dataclass(frozen=True)
class CompositionZone:
    """Semantic zone within a page — guides reading order, not pixel placement."""

    role: str
    position_hint: str
    description: str = ""


@dataclass(frozen=True)
class VisualPageRecipe:
    """Visual strategy recipe for one page archetype."""

    archetype: PageArchetype
    display_name: str
    composition_zones: tuple[CompositionZone, ...]
    reading_order: tuple[str, ...]
    preferred_layout_families: tuple[LayoutFamily, ...]
    preferred_variants: tuple[tuple[LayoutFamily, str], ...]
    forbidden_layout_families: frozenset[LayoutFamily]
    dominant_content_type: VisualContentType
    continuity_role: ContinuityRole
    default_density: DensityLevel
    image_treatment: str
    annotation_strategy: str
    composition_strategy: str
    emotional_tone: str
    title_signals: tuple[ArchetypeSignal, ...] = ()
    body_signals: tuple[ArchetypeSignal, ...] = ()
    visual_type_hints: frozenset[VisualType] = frozenset()
    slide_type_hints: frozenset[SlideType] = frozenset()


def _sig(pattern: str, weight: float = 1.0, label: str = "") -> ArchetypeSignal:
    return ArchetypeSignal(re.compile(pattern, re.I), weight=weight, label=label or pattern)


_VISUAL_GRAMMAR: dict[PageArchetype, VisualPageRecipe] = {
    PageArchetype.SITE_CONTEXT_ANALYSIS: VisualPageRecipe(
        archetype=PageArchetype.SITE_CONTEXT_ANALYSIS,
        display_name="区位分析",
        composition_zones=(
            CompositionZone("map_hero", "center-left", "区位/基地地图为主视觉"),
            CompositionZone("traffic_overlay", "map_overlay", "交通/可达性叠加"),
            CompositionZone("scale_relation", "bottom-left", "尺度关系/图例"),
            CompositionZone("conclusion", "bottom-right", "区位结论收束"),
        ),
        reading_order=("map", "traffic", "scale", "conclusion"),
        preferred_layout_families=(
            LayoutFamily.HYBRID_CANVAS,
            LayoutFamily.DRAWING_FOCUS,
        ),
        preferred_variants=(
            (LayoutFamily.DRAWING_FOCUS, "drawing_with_annotations"),
            (LayoutFamily.HYBRID_CANVAS, "freeform"),
        ),
        forbidden_layout_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.STRATEGY_CARDS, LayoutFamily.METRIC_DASHBOARD}
        ),
        dominant_content_type=VisualContentType.SITE_PLAN,
        continuity_role=ContinuityRole.EXPLANATION,
        default_density=DensityLevel.BALANCED,
        image_treatment="drawing_contain",
        annotation_strategy="交通/尺度标注叠加于地图",
        composition_strategy="地图主导 + 交通/尺度叠加 + 结论收束",
        emotional_tone="分析中性",
        title_signals=(
            _sig(r"区位|基地|场地|site\s*context|location\s*analysis", 2.0, "区位标题"),
            _sig(r"交通|可达|周边|connectivity|access", 1.5, "交通标题"),
        ),
        body_signals=(
            _sig(r"区位|基地|场地|周边|context", 1.2),
            _sig(r"交通|地铁|道路|可达|access|transit", 1.5),
            _sig(r"尺度|比例|关系|scale|relation", 1.2),
            _sig(r"地图|总图|map|site\s*plan", 1.8),
        ),
        visual_type_hints=frozenset({VisualType.MAP, VisualType.SITE_PLAN}),
    ),
    PageArchetype.SITE_PROBLEM_DIAGNOSIS: VisualPageRecipe(
        archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS,
        display_name="现状问题",
        composition_zones=(
            CompositionZone("site_photos", "left", "现场照片/证据"),
            CompositionZone("problem_tags", "right", "问题标签/编号"),
            CompositionZone("analysis", "bottom", "分析结论"),
        ),
        reading_order=("title", "photos", "tags", "analysis", "conclusion"),
        preferred_layout_families=(
            LayoutFamily.EVIDENCE_BOARD,
            LayoutFamily.ANALYTICAL_DIAGRAM,
        ),
        preferred_variants=(
            (LayoutFamily.EVIDENCE_BOARD, "numbered_grid"),
            (LayoutFamily.EVIDENCE_BOARD, "journey_with_photos"),
        ),
        forbidden_layout_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.STRATEGY_CARDS, LayoutFamily.METRIC_DASHBOARD}
        ),
        dominant_content_type=VisualContentType.PHOTO_EVIDENCE,
        continuity_role=ContinuityRole.EVIDENCE,
        default_density=DensityLevel.COMPACT,
        image_treatment="photo_cover",
        annotation_strategy="编号对应问题标签",
        composition_strategy="左：现场照片；右：问题标签；底部：分析结论",
        emotional_tone="诊断警示",
        title_signals=(
            _sig(r"现状|问题|诊断|痛点|problem|diagnosis|issue", 2.0, "问题标题"),
            _sig(r"现场|证据|evidence", 1.5),
        ),
        body_signals=(
            _sig(r"现状|问题|不足|缺陷|矛盾|problem|issue|pain", 1.8),
            _sig(r"照片|现场|photo|site", 1.5),
            _sig(r"编号|标注|label|tag", 1.0),
        ),
        visual_type_hints=frozenset({VisualType.SITE_PHOTO}),
        slide_type_hints=frozenset({SlideType.IMAGE}),
    ),
    PageArchetype.DESIGN_STRATEGY: VisualPageRecipe(
        archetype=PageArchetype.DESIGN_STRATEGY,
        display_name="设计策略",
        composition_zones=(
            CompositionZone("strategy_keywords", "top", "策略关键词/原则"),
            CompositionZone("concept_diagram", "center", "概念图/逻辑示意"),
            CompositionZone("logic_flow", "center-overlay", "逻辑箭头/因果关系"),
            CompositionZone("spatial_change", "bottom", "空间变化/实施路径"),
        ),
        reading_order=("keywords", "concept", "logic", "spatial_change"),
        preferred_layout_families=(
            LayoutFamily.STRATEGY_CARDS,
            LayoutFamily.ANALYTICAL_DIAGRAM,
            LayoutFamily.PROCESS_NARRATIVE,
        ),
        preferred_variants=(
            (LayoutFamily.STRATEGY_CARDS, "cards_with_lead"),
            (LayoutFamily.STRATEGY_CARDS, "three_cards"),
            (LayoutFamily.ANALYTICAL_DIAGRAM, "diagram_with_callouts"),
        ),
        forbidden_layout_families=frozenset({LayoutFamily.HERO, LayoutFamily.EVIDENCE_BOARD}),
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        continuity_role=ContinuityRole.EXPLANATION,
        default_density=DensityLevel.BALANCED,
        image_treatment="diagram_contain",
        annotation_strategy="策略关键词与概念图对应",
        composition_strategy="策略关键词 + 概念图 + 逻辑箭头 + 空间变化",
        emotional_tone="策略自信",
        title_signals=(
            _sig(r"策略|原则|概念|目标|strategy|concept|approach", 2.0, "策略标题"),
            _sig(r"设计思路|design\s*intent", 1.8),
        ),
        body_signals=(
            _sig(r"策略|原则|目标|concept|strategy|principle", 1.8),
            _sig(r"空间|改造|介入|intervention|spatial", 1.2),
            _sig(r"逻辑|关系|箭头|flow|logic", 1.0),
        ),
        visual_type_hints=frozenset({VisualType.DIAGRAM, VisualType.TEXT_ONLY}),
    ),
    PageArchetype.BEFORE_AFTER_TRANSFORMATION: VisualPageRecipe(
        archetype=PageArchetype.BEFORE_AFTER_TRANSFORMATION,
        display_name="改造前后",
        composition_zones=(
            CompositionZone("before", "left", "改造前状态"),
            CompositionZone("after", "right", "改造后状态"),
            CompositionZone("insight", "bottom", "对比结论/变化说明"),
        ),
        reading_order=("before", "after", "insight"),
        preferred_layout_families=(LayoutFamily.COMPARATIVE_MATRIX,),
        preferred_variants=((LayoutFamily.COMPARATIVE_MATRIX, "before_after"),),
        forbidden_layout_families=frozenset(
            {LayoutFamily.HERO, LayoutFamily.STRATEGY_CARDS, LayoutFamily.TEXTUAL_ARGUMENT}
        ),
        dominant_content_type=VisualContentType.COMPARISON,
        continuity_role=ContinuityRole.COMPARISON,
        default_density=DensityLevel.BALANCED,
        image_treatment="photo_contain",
        annotation_strategy="前后对照标注",
        composition_strategy="Before / After 等权对照 + 底部变化结论",
        emotional_tone="对比中性",
        title_signals=(
            _sig(r"前后|改造|对比|before\s*after|transformation", 2.5, "前后标题"),
        ),
        body_signals=(
            _sig(r"前后|改造|对比|before|after|transformation", 2.0),
            _sig(r"变化|提升|改善|change|improve", 1.0),
        ),
        visual_type_hints=frozenset({VisualType.COMPARISON, VisualType.SITE_PHOTO}),
        slide_type_hints=frozenset({SlideType.COMPARISON}),
    ),
    PageArchetype.GENERIC: VisualPageRecipe(
        archetype=PageArchetype.GENERIC,
        display_name="通用内容",
        composition_zones=(),
        reading_order=("title", "hero", "supporting", "source"),
        preferred_layout_families=(LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.HYBRID_CANVAS),
        preferred_variants=(),
        forbidden_layout_families=frozenset(),
        dominant_content_type=VisualContentType.MIXED,
        continuity_role=ContinuityRole.EXPLANATION,
        default_density=DensityLevel.BALANCED,
        image_treatment="photo_cover",
        annotation_strategy="图注补充",
        composition_strategy="按内容类型选择版式",
        emotional_tone="克制专业",
    ),
}


def get_visual_grammar_registry() -> dict[PageArchetype, VisualPageRecipe]:
    """Return the canonical visual grammar registry (read-only view)."""
    return dict(_VISUAL_GRAMMAR)


def get_recipe(archetype: PageArchetype) -> VisualPageRecipe:
    """Lookup recipe; unknown archetypes fall back to GENERIC."""
    return _VISUAL_GRAMMAR.get(archetype, _VISUAL_GRAMMAR[PageArchetype.GENERIC])
