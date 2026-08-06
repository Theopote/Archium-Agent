"""Architectural Visual Grammar Library (VQ-005).

Product grammars answer “what should this page *look like* as architectural
speech?” — not LayoutFamily function labels. Each profile binds typography,
color, motif, and layout preferences into one executable package.

P0 showcase set (must visibly change the page):
  monumental_statement, architectural_editorial, analytical_overlay,
  drawing_atlas, metric_monument

Full catalog targets the 12 grammars from Visual Quality Recovery.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.page_visual_grammar import PageGrammarId
from archium.domain.visual.visual_language.color_composition import (
    BackgroundMode,
    ColorArrangement,
)
from archium.domain.visual.visual_language.graphic_motif import MotifType
from archium.domain.visual.visual_language.typography_composition import TypographyPageKind


class ArchitecturalGrammarId(StrEnum):
    """Stable product grammar ids — the twelve VQ-005 languages."""

    MONUMENTAL_STATEMENT = "monumental_statement"
    ARCHITECTURAL_EDITORIAL = "architectural_editorial"
    ANALYTICAL_OVERLAY = "analytical_overlay"
    DRAWING_ATLAS = "drawing_atlas"
    SPATIAL_SEQUENCE = "spatial_sequence"
    BEFORE_INTERVENTION_AFTER = "before_intervention_after"
    METRIC_MONUMENT = "metric_monument"
    CONCEPT_COLLAGE = "concept_collage"
    STRATEGY_CONSTELLATION = "strategy_constellation"
    MATERIAL_PALETTE = "material_palette"
    TIMELINE_RIBBON = "timeline_ribbon"
    FINAL_VISION = "final_vision"


class CompositionStrategy(StrEnum):
    """Page composition behavior — orthogonal to LayoutFamily."""

    STRICT_GRID = "strict_grid"
    BROKEN_GRID = "broken_grid"
    ASYMMETRIC_BALANCE = "asymmetric_balance"
    CENTERED_MONUMENTAL = "centered_monumental"
    EDGE_TENSION = "edge_tension"
    OVERLAP_COLLAGE = "overlap_collage"
    FULL_BLEED = "full_bleed"
    FLOATING_ISLANDS = "floating_islands"
    VERTICAL_SEQUENCE = "vertical_sequence"
    RADIAL_FOCUS = "radial_focus"
    DIAGONAL_FLOW = "diagonal_flow"
    LAYERED_DEPTH = "layered_depth"


class ArchitecturalVisualGrammar(DomainModel):
    """Executable grammar profile — drives Visual Language + layout preference."""

    grammar_id: ArchitecturalGrammarId
    display_name: str = Field(min_length=1, max_length=80)
    display_name_zh: str = Field(min_length=1, max_length=80)
    # Link into existing PageVisualFormula catalog when applicable.
    formula_ids: list[PageGrammarId] = Field(default_factory=list, max_length=4)
    applicable_page_kinds: list[TypographyPageKind] = Field(default_factory=list)
    forbidden_conditions: list[str] = Field(default_factory=list, max_length=8)
    required_content: list[str] = Field(default_factory=list, max_length=8)
    visual_traits: list[str] = Field(default_factory=list, max_length=10)

    preferred_families: list[LayoutFamily] = Field(default_factory=list, max_length=4)
    preferred_variants: list[str] = Field(default_factory=list, max_length=6)
    composition_strategy: CompositionStrategy = CompositionStrategy.ASYMMETRIC_BALANCE

    typography_page_kind: TypographyPageKind = TypographyPageKind.DEFAULT
    title_size_boost: float = Field(default=1.0, ge=0.8, le=2.0)
    letter_spacing_em: float = Field(default=0.03, ge=-0.05, le=0.2)
    background_mode: BackgroundMode = BackgroundMode.TINTED
    color_arrangement: ColorArrangement | None = Field(
        default=None,
        description="VQ-005 v1.1: preferred ColorComposition arrangement.",
    )
    accent_ratio: float = Field(default=0.06, ge=0.02, le=0.3)
    motif_type: MotifType = MotifType.QUIET_RULE
    hero_min_ratio: float | None = Field(default=None, ge=0.35, le=0.9)
    # Soft density: sparse pages refuse key-point walls.
    max_key_points: int = Field(default=4, ge=0, le=8)
    p0_showcase: bool = False
    source: str = Field(default="vq5_grammar_v1", max_length=40)

    def as_dict(self) -> dict[str, object]:
        return {
            "grammar_id": self.grammar_id.value,
            "display_name": self.display_name,
            "display_name_zh": self.display_name_zh,
            "formula_ids": [f.value for f in self.formula_ids],
            "applicable_page_kinds": [k.value for k in self.applicable_page_kinds],
            "forbidden_conditions": list(self.forbidden_conditions),
            "required_content": list(self.required_content),
            "visual_traits": list(self.visual_traits),
            "preferred_families": [f.value for f in self.preferred_families],
            "preferred_variants": list(self.preferred_variants),
            "composition_strategy": self.composition_strategy.value,
            "typography_page_kind": self.typography_page_kind.value,
            "title_size_boost": self.title_size_boost,
            "letter_spacing_em": self.letter_spacing_em,
            "background_mode": self.background_mode.value,
            "color_arrangement": (
                self.color_arrangement.value if self.color_arrangement else None
            ),
            "accent_ratio": self.accent_ratio,
            "motif_type": self.motif_type.value,
            "hero_min_ratio": self.hero_min_ratio,
            "max_key_points": self.max_key_points,
            "p0_showcase": self.p0_showcase,
            "source": self.source,
        }


# --- Catalog -----------------------------------------------------------------

GRAMMAR_MONUMENTAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.MONUMENTAL_STATEMENT,
    display_name="Monumental Statement",
    display_name_zh="纪念碑主张",
    formula_ids=[PageGrammarId.MONUMENT_IMAGE, PageGrammarId.HERO_STATEMENT],
    applicable_page_kinds=[
        TypographyPageKind.COVER,
        TypographyPageKind.THESIS,
        TypographyPageKind.CLOSING,
    ],
    forbidden_conditions=["key_point_wall", "metric_wall", "dense_body"],
    required_content=["one_claim", "hero_or_void"],
    visual_traits=["oversized_title", "extreme_whitespace", "single_focus"],
    preferred_families=[LayoutFamily.HERO, LayoutFamily.TEXTUAL_ARGUMENT],
    preferred_variants=["full_bleed", "monument", "overlay"],
    composition_strategy=CompositionStrategy.CENTERED_MONUMENTAL,
    typography_page_kind=TypographyPageKind.COVER,
    title_size_boost=1.55,
    letter_spacing_em=0.08,
    background_mode=BackgroundMode.DARK,
    color_arrangement=ColorArrangement.ACCENT_EDGE,
    accent_ratio=0.08,
    motif_type=MotifType.QUIET_RULE,
    hero_min_ratio=0.65,
    max_key_points=0,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_EDITORIAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL,
    display_name="Architectural Editorial",
    display_name_zh="建筑编辑式",
    formula_ids=[PageGrammarId.QUIET_ARGUMENT, PageGrammarId.SECTION_OPENER],
    applicable_page_kinds=[
        TypographyPageKind.SECTION,
        TypographyPageKind.THESIS,
        TypographyPageKind.DEFAULT,
    ],
    forbidden_conditions=["symmetric_card_wall", "equal_photo_grid"],
    required_content=["asymmetric_title", "margin_index"],
    visual_traits=["broken_grid", "small_caption", "editorial_number"],
    preferred_families=[LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.HYBRID_CANVAS],
    preferred_variants=["section_opener", "quote_argument", "lead_and_points"],
    composition_strategy=CompositionStrategy.ASYMMETRIC_BALANCE,
    typography_page_kind=TypographyPageKind.SECTION,
    title_size_boost=1.25,
    letter_spacing_em=0.1,
    background_mode=BackgroundMode.LIGHT,
    color_arrangement=ColorArrangement.TOP_MASTHEAD,
    accent_ratio=0.04,
    motif_type=MotifType.SECTION_CUT,
    hero_min_ratio=0.4,
    max_key_points=3,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_ANALYTICAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.ANALYTICAL_OVERLAY,
    display_name="Analytical Overlay",
    display_name_zh="分析叠层",
    formula_ids=[PageGrammarId.LAYER_ANALYSIS, PageGrammarId.PATH_EXPERIENCE],
    applicable_page_kinds=[TypographyPageKind.DEFAULT, TypographyPageKind.THESIS],
    forbidden_conditions=["decorative_party", "text_wall"],
    required_content=["base_map", "overlay", "callouts"],
    visual_traits=["translucent_blocks", "leaders", "numbered_nodes", "legend"],
    preferred_families=[
        LayoutFamily.ANALYTICAL_DIAGRAM,
        LayoutFamily.DRAWING_FOCUS,
    ],
    preferred_variants=["default", "flow", "overlay"],
    composition_strategy=CompositionStrategy.LAYERED_DEPTH,
    typography_page_kind=TypographyPageKind.DEFAULT,
    title_size_boost=1.1,
    letter_spacing_em=0.04,
    background_mode=BackgroundMode.LIGHT,
    color_arrangement=ColorArrangement.BOTTOM_WASH,
    accent_ratio=0.12,
    motif_type=MotifType.FLOW_NODES,
    hero_min_ratio=0.55,
    max_key_points=2,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_DRAWING_ATLAS = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.DRAWING_ATLAS,
    display_name="Drawing Atlas",
    display_name_zh="图纸图集",
    formula_ids=[PageGrammarId.DRAWING_DOMINANT, PageGrammarId.MASTERPLAN_FOCUS],
    applicable_page_kinds=[TypographyPageKind.DEFAULT],
    forbidden_conditions=["cover_crop_drawing", "equal_text_image_split"],
    required_content=["primary_drawing", "keyed_notes", "scale"],
    visual_traits=["drawing_dominant", "strict_align", "thin_annotations"],
    preferred_families=[LayoutFamily.DRAWING_FOCUS],
    preferred_variants=["drawing_with_callouts", "drawing_with_metrics", "default"],
    composition_strategy=CompositionStrategy.STRICT_GRID,
    typography_page_kind=TypographyPageKind.DEFAULT,
    title_size_boost=1.05,
    letter_spacing_em=0.06,
    background_mode=BackgroundMode.LIGHT,
    color_arrangement=ColorArrangement.MONO_RULE,
    accent_ratio=0.05,
    motif_type=MotifType.AXIS_GRID,
    hero_min_ratio=0.72,
    max_key_points=2,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_SPATIAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.SPATIAL_SEQUENCE,
    display_name="Spatial Sequence",
    display_name_zh="空间序列",
    formula_ids=[PageGrammarId.PATH_EXPERIENCE, PageGrammarId.THRESHOLD_SEQUENCE],
    applicable_page_kinds=[TypographyPageKind.DEFAULT, TypographyPageKind.THESIS],
    forbidden_conditions=["unordered_photo_dump"],
    required_content=["path", "ordered_nodes", "start_end"],
    visual_traits=["path_line", "sequence_numbers", "directional_flow"],
    preferred_families=[
        LayoutFamily.PROCESS_NARRATIVE,
        LayoutFamily.ANALYTICAL_DIAGRAM,
    ],
    preferred_variants=["default", "flow"],
    composition_strategy=CompositionStrategy.VERTICAL_SEQUENCE,
    typography_page_kind=TypographyPageKind.DEFAULT,
    title_size_boost=1.15,
    letter_spacing_em=0.04,
    background_mode=BackgroundMode.TINTED,
    color_arrangement=ColorArrangement.PLAIN,
    accent_ratio=0.1,
    motif_type=MotifType.PATH_SEQUENCE,
    hero_min_ratio=0.5,
    max_key_points=3,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_BEFORE_AFTER = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.BEFORE_INTERVENTION_AFTER,
    display_name="Before / Intervention / After",
    display_name_zh="原状 / 介入 / 更新",
    formula_ids=[PageGrammarId.BEFORE_AFTER_CUT, PageGrammarId.STRATEGY_EXISTING_TRANSFORM],
    applicable_page_kinds=[TypographyPageKind.THESIS, TypographyPageKind.DEFAULT],
    forbidden_conditions=["identical_filters"],
    required_content=["before", "intervention_accent", "after"],
    visual_traits=["gray_existing", "accent_cut", "color_after"],
    preferred_families=[LayoutFamily.COMPARATIVE_MATRIX, LayoutFamily.HYBRID_CANVAS],
    preferred_variants=["before_after", "default"],
    composition_strategy=CompositionStrategy.DIAGONAL_FLOW,
    typography_page_kind=TypographyPageKind.THESIS,
    title_size_boost=1.2,
    letter_spacing_em=0.03,
    background_mode=BackgroundMode.TINTED,
    color_arrangement=ColorArrangement.ACCENT_EDGE,
    accent_ratio=0.14,
    motif_type=MotifType.BEFORE_AFTER_SLICE,
    hero_min_ratio=0.55,
    max_key_points=2,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_METRIC = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.METRIC_MONUMENT,
    display_name="Metric Monument",
    display_name_zh="指标纪念碑",
    formula_ids=[PageGrammarId.DECISION_METRIC],
    applicable_page_kinds=[TypographyPageKind.METRIC],
    forbidden_conditions=["metric_wall", "tiny_equal_cards"],
    required_content=["giant_number", "small_label"],
    visual_traits=["number_as_hero", "sparse_support", "accent_figure"],
    preferred_families=[LayoutFamily.METRIC_DASHBOARD, LayoutFamily.TEXTUAL_ARGUMENT],
    preferred_variants=["metric_cards", "monument"],
    composition_strategy=CompositionStrategy.CENTERED_MONUMENTAL,
    typography_page_kind=TypographyPageKind.METRIC,
    title_size_boost=1.15,
    letter_spacing_em=0.02,
    background_mode=BackgroundMode.LIGHT,
    color_arrangement=ColorArrangement.METRIC_PANEL,
    accent_ratio=0.16,
    motif_type=MotifType.MODULE_INDEX,
    hero_min_ratio=None,
    max_key_points=1,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

GRAMMAR_COLLAGE = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.CONCEPT_COLLAGE,
    display_name="Concept Collage",
    display_name_zh="概念拼贴",
    formula_ids=[PageGrammarId.CORE_EXPANSION],
    applicable_page_kinds=[TypographyPageKind.THESIS, TypographyPageKind.COVER],
    forbidden_conditions=["strict_equal_grid"],
    required_content=["fragments", "keywords", "overlay"],
    visual_traits=["overlap", "translucent_layers", "hand_line_feel"],
    preferred_families=[LayoutFamily.HYBRID_CANVAS, LayoutFamily.STRATEGY_CARDS],
    preferred_variants=["default", "overlay"],
    composition_strategy=CompositionStrategy.OVERLAP_COLLAGE,
    typography_page_kind=TypographyPageKind.THESIS,
    title_size_boost=1.35,
    letter_spacing_em=0.02,
    background_mode=BackgroundMode.ACCENT_WASH,
    color_arrangement=ColorArrangement.BOTTOM_WASH,
    accent_ratio=0.18,
    motif_type=MotifType.MODULE_INDEX,
    hero_min_ratio=0.45,
    max_key_points=4,
    p0_showcase=False,
    source="vq5_grammar_v1_1",
)

GRAMMAR_STRATEGY = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.STRATEGY_CONSTELLATION,
    display_name="Strategy Constellation",
    display_name_zh="策略星座",
    formula_ids=[PageGrammarId.STRATEGY_EXISTING_TRANSFORM, PageGrammarId.CORE_EXPANSION],
    applicable_page_kinds=[TypographyPageKind.THESIS, TypographyPageKind.DEFAULT],
    forbidden_conditions=["flat_equal_cards"],
    required_content=["center_concept", "radial_nodes", "links"],
    visual_traits=["radial", "hierarchy", "connectors"],
    preferred_families=[LayoutFamily.STRATEGY_CARDS, LayoutFamily.ANALYTICAL_DIAGRAM],
    preferred_variants=["default"],
    composition_strategy=CompositionStrategy.RADIAL_FOCUS,
    typography_page_kind=TypographyPageKind.THESIS,
    title_size_boost=1.2,
    letter_spacing_em=0.04,
    background_mode=BackgroundMode.TINTED,
    color_arrangement=ColorArrangement.TOP_MASTHEAD,
    accent_ratio=0.1,
    motif_type=MotifType.FLOW_NODES,
    hero_min_ratio=0.4,
    max_key_points=4,
    p0_showcase=False,
    source="vq5_grammar_v1_1",
)

GRAMMAR_MATERIAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.MATERIAL_PALETTE,
    display_name="Material Palette",
    display_name_zh="材料色板",
    formula_ids=[PageGrammarId.PROGRAM_STACK],
    applicable_page_kinds=[TypographyPageKind.DEFAULT],
    forbidden_conditions=["unlabeled_swatches"],
    required_content=["swatches", "detail_photos", "indexes"],
    visual_traits=["swatch_row", "indexed_samples", "facade_link"],
    preferred_families=[LayoutFamily.EVIDENCE_BOARD, LayoutFamily.HYBRID_CANVAS],
    preferred_variants=["default"],
    composition_strategy=CompositionStrategy.STRICT_GRID,
    typography_page_kind=TypographyPageKind.DEFAULT,
    title_size_boost=1.1,
    letter_spacing_em=0.08,
    background_mode=BackgroundMode.LIGHT,
    color_arrangement=ColorArrangement.MONO_RULE,
    accent_ratio=0.08,
    motif_type=MotifType.MODULE_INDEX,
    hero_min_ratio=0.45,
    max_key_points=3,
    p0_showcase=False,
    source="vq5_grammar_v1_1",
)

GRAMMAR_TIMELINE = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.TIMELINE_RIBBON,
    display_name="Timeline Ribbon",
    display_name_zh="时间色带",
    formula_ids=[PageGrammarId.PHASING_TIMELINE, PageGrammarId.PROCESS_SEQUENCE],
    applicable_page_kinds=[TypographyPageKind.DEFAULT],
    forbidden_conditions=["unordered_milestones"],
    required_content=["ribbon", "phase_nodes", "dates"],
    visual_traits=["continuous_band", "phase_color", "photo_slices"],
    preferred_families=[LayoutFamily.PROCESS_NARRATIVE],
    preferred_variants=["default"],
    composition_strategy=CompositionStrategy.DIAGONAL_FLOW,
    typography_page_kind=TypographyPageKind.DEFAULT,
    title_size_boost=1.1,
    letter_spacing_em=0.05,
    background_mode=BackgroundMode.TINTED,
    color_arrangement=ColorArrangement.BOTTOM_WASH,
    accent_ratio=0.12,
    motif_type=MotifType.PATH_SEQUENCE,
    hero_min_ratio=0.4,
    max_key_points=4,
    p0_showcase=False,
    source="vq5_grammar_v1_1",
)

GRAMMAR_FINAL = ArchitecturalVisualGrammar(
    grammar_id=ArchitecturalGrammarId.FINAL_VISION,
    display_name="Final Vision",
    display_name_zh="终章愿景",
    formula_ids=[PageGrammarId.HERO_STATEMENT, PageGrammarId.QUIET_ARGUMENT],
    applicable_page_kinds=[TypographyPageKind.CLOSING, TypographyPageKind.COVER],
    forbidden_conditions=["new_arguments", "dense_metrics"],
    required_content=["hero_image", "one_claim", "project_meta"],
    visual_traits=["full_bleed", "quiet_type", "minimal_chrome"],
    preferred_families=[LayoutFamily.HERO, LayoutFamily.TEXTUAL_ARGUMENT],
    preferred_variants=["full_bleed", "monument"],
    composition_strategy=CompositionStrategy.FULL_BLEED,
    typography_page_kind=TypographyPageKind.CLOSING,
    title_size_boost=1.45,
    letter_spacing_em=0.12,
    background_mode=BackgroundMode.DARK,
    color_arrangement=ColorArrangement.CLOSING_FIELD,
    accent_ratio=0.05,
    motif_type=MotifType.QUIET_RULE,
    hero_min_ratio=0.7,
    max_key_points=0,
    p0_showcase=True,
    source="vq5_grammar_v1_1",
)

_GRAMMARS: dict[ArchitecturalGrammarId, ArchitecturalVisualGrammar] = {
    g.grammar_id: g
    for g in (
        GRAMMAR_MONUMENTAL,
        GRAMMAR_EDITORIAL,
        GRAMMAR_ANALYTICAL,
        GRAMMAR_DRAWING_ATLAS,
        GRAMMAR_SPATIAL,
        GRAMMAR_BEFORE_AFTER,
        GRAMMAR_METRIC,
        GRAMMAR_COLLAGE,
        GRAMMAR_STRATEGY,
        GRAMMAR_MATERIAL,
        GRAMMAR_TIMELINE,
        GRAMMAR_FINAL,
    )
}

_FORMULA_TO_GRAMMAR: dict[PageGrammarId, ArchitecturalGrammarId] = {
    PageGrammarId.MONUMENT_IMAGE: ArchitecturalGrammarId.MONUMENTAL_STATEMENT,
    PageGrammarId.HERO_STATEMENT: ArchitecturalGrammarId.MONUMENTAL_STATEMENT,
    PageGrammarId.QUIET_ARGUMENT: ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL,
    PageGrammarId.SECTION_OPENER: ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL,
    PageGrammarId.LAYER_ANALYSIS: ArchitecturalGrammarId.ANALYTICAL_OVERLAY,
    PageGrammarId.AXONOMETRIC_CALLOUT: ArchitecturalGrammarId.ANALYTICAL_OVERLAY,
    PageGrammarId.DRAWING_DOMINANT: ArchitecturalGrammarId.DRAWING_ATLAS,
    PageGrammarId.MASTERPLAN_FOCUS: ArchitecturalGrammarId.DRAWING_ATLAS,
    PageGrammarId.PATH_EXPERIENCE: ArchitecturalGrammarId.SPATIAL_SEQUENCE,
    PageGrammarId.THRESHOLD_SEQUENCE: ArchitecturalGrammarId.SPATIAL_SEQUENCE,
    PageGrammarId.BEFORE_AFTER_CUT: ArchitecturalGrammarId.BEFORE_INTERVENTION_AFTER,
    PageGrammarId.STRATEGY_EXISTING_TRANSFORM: ArchitecturalGrammarId.STRATEGY_CONSTELLATION,
    PageGrammarId.DECISION_METRIC: ArchitecturalGrammarId.METRIC_MONUMENT,
    PageGrammarId.CORE_EXPANSION: ArchitecturalGrammarId.CONCEPT_COLLAGE,
    PageGrammarId.PROGRAM_STACK: ArchitecturalGrammarId.MATERIAL_PALETTE,
    PageGrammarId.PHASING_TIMELINE: ArchitecturalGrammarId.TIMELINE_RIBBON,
    PageGrammarId.PROCESS_SEQUENCE: ArchitecturalGrammarId.TIMELINE_RIBBON,
    PageGrammarId.PROBLEM_EVIDENCE_CONFLICT: ArchitecturalGrammarId.ANALYTICAL_OVERLAY,
    PageGrammarId.EVIDENCE_TRIPTYCH: ArchitecturalGrammarId.ANALYTICAL_OVERLAY,
    PageGrammarId.QUOTE_CITATION: ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL,
}


def get_architectural_grammar(
    grammar_id: ArchitecturalGrammarId | str,
) -> ArchitecturalVisualGrammar:
    key = (
        grammar_id
        if isinstance(grammar_id, ArchitecturalGrammarId)
        else ArchitecturalGrammarId(str(grammar_id))
    )
    return _GRAMMARS[key]


def list_architectural_grammars(*, p0_only: bool = False) -> list[ArchitecturalVisualGrammar]:
    grammars = list(_GRAMMARS.values())
    if p0_only:
        return [g for g in grammars if g.p0_showcase]
    return grammars


def grammar_for_formula(formula_id: PageGrammarId | str) -> ArchitecturalVisualGrammar:
    key = (
        formula_id
        if isinstance(formula_id, PageGrammarId)
        else PageGrammarId(str(formula_id))
    )
    grammar_id = _FORMULA_TO_GRAMMAR.get(key, ArchitecturalGrammarId.ARCHITECTURAL_EDITORIAL)
    return _GRAMMARS[grammar_id]
