"""PageDirectionService — rule-first page creative director (Visual seat).

Produces structured PageDirection (no coordinates). Prefers deterministic
situation rules; optional LLM may only fill structured fields later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from archium.domain.slide import SlideSpec
from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_composition import SlideCompositionDirective
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.page_direction import (
    CompositionBias,
    CopyBudget,
    PageDirection,
)
from archium.domain.visual.style import StylePreset, get_style_preset
from archium.domain.visual.visual_grammar import (
    PageArchetype,
    VisualPageRecipe,
    get_recipe,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry


@dataclass(frozen=True)
class _SituationRule:
    rule_id: str
    patterns: tuple[re.Pattern[str], ...]
    must_show: tuple[str, ...]
    must_hide: tuple[str, ...]
    composition_bias: tuple[CompositionBias, ...]
    preferred: tuple[LayoutFamily, ...]
    forbidden: tuple[LayoutFamily, ...]
    density: DensityLevel
    copy_budget: CopyBudget
    label: str


def _pat(*exprs: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(expr, re.I) for expr in exprs)


_SITUATION_RULES: tuple[_SituationRule, ...] = (
    _SituationRule(
        rule_id="site_traffic_conflict",
        patterns=_pat(
            r"人车混行",
            r"交通复杂",
            r"车流.{0,8}人流",
            r"人流.{0,8}车流",
            r"混行",
            r"交叉口拥堵",
            r"交通冲突",
        ),
        must_show=("site_photo", "circulation_diagram", "problem_conclusion"),
        must_hide=("long_body_paragraphs", "three_column_text", "metric_wall"),
        composition_bias=(
            CompositionBias.PHOTO_LEFT,
            CompositionBias.DIAGRAM_CENTER,
            CompositionBias.CONCLUSION_BAR,
        ),
        preferred=(
            LayoutFamily.EVIDENCE_BOARD,
            LayoutFamily.ANALYTICAL_DIAGRAM,
            LayoutFamily.HYBRID_CANVAS,
        ),
        forbidden=(
            LayoutFamily.TEXTUAL_ARGUMENT,
            LayoutFamily.METRIC_DASHBOARD,
            LayoutFamily.STRATEGY_CARDS,
        ),
        density=DensityLevel.BALANCED,
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=72,
            max_key_points=1,
            max_body_blocks=1,
        ),
        label="基地交通矛盾：一图一流线一句结论",
    ),
    _SituationRule(
        rule_id="site_problem_evidence",
        patterns=_pat(
            r"现状问题",
            r"痛点",
            r"现场问题",
            r"老化",
            r"破损",
            r"隐患",
            r"evidence\s*board",
        ),
        must_show=("photo_evidence_grid", "issue_labels", "problem_conclusion"),
        must_hide=("long_body_paragraphs", "decorative_icons"),
        composition_bias=(
            CompositionBias.EVIDENCE_GRID,
            CompositionBias.CONCLUSION_BAR,
        ),
        preferred=(LayoutFamily.EVIDENCE_BOARD, LayoutFamily.HYBRID_CANVAS),
        forbidden=(LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.METRIC_DASHBOARD),
        density=DensityLevel.COMPACT,
        copy_budget=CopyBudget(
            max_title_chars=32,
            max_message_chars=90,
            max_key_points=4,
            max_body_blocks=1,
        ),
        label="现状证据板：照片网格 + 短结论",
    ),
    _SituationRule(
        rule_id="drawing_story",
        patterns=_pat(
            r"总平面",
            r"总图",
            r"平面图",
            r"立面",
            r"剖面",
            r"master\s*plan",
            r"floor\s*plan",
        ),
        must_show=("primary_drawing", "north_arrow", "keyed_annotations"),
        must_hide=("photo_wall", "three_column_text"),
        composition_bias=(CompositionBias.DRAWING_DOMINANT,),
        preferred=(LayoutFamily.DRAWING_FOCUS, LayoutFamily.ANALYTICAL_DIAGRAM),
        forbidden=(LayoutFamily.HERO, LayoutFamily.METRIC_DASHBOARD),
        density=DensityLevel.COMPACT,
        copy_budget=CopyBudget(
            max_title_chars=30,
            max_message_chars=80,
            max_key_points=3,
            max_body_blocks=1,
        ),
        label="图纸叙事：主图 + 编号解释",
    ),
    _SituationRule(
        rule_id="strategy_cards",
        patterns=_pat(r"设计策略", r"策略要点", r"三大策略", r"四项策略", r"strategy"),
        must_show=("strategy_cards", "one_line_thesis"),
        must_hide=("long_body_paragraphs", "dense_bullet_wall"),
        composition_bias=(CompositionBias.STRATEGY_CARDS,),
        preferred=(LayoutFamily.STRATEGY_CARDS, LayoutFamily.HYBRID_CANVAS),
        forbidden=(LayoutFamily.TEXTUAL_ARGUMENT, LayoutFamily.EVIDENCE_BOARD),
        density=DensityLevel.BALANCED,
        copy_budget=CopyBudget(
            max_title_chars=28,
            max_message_chars=64,
            max_key_points=4,
            max_body_blocks=0,
        ),
        label="策略卡：3–4 卡，禁止堆字",
    ),
    _SituationRule(
        rule_id="hero_opening",
        patterns=_pat(r"^封面", r"开篇", r"项目愿景", r"概念宣言", r"hero\s*opening"),
        must_show=("hero_image", "one_line_concept"),
        must_hide=("key_point_list", "metric_wall", "dense_caption"),
        composition_bias=(CompositionBias.HERO_FULL,),
        preferred=(LayoutFamily.HERO, LayoutFamily.HYBRID_CANVAS),
        forbidden=(
            LayoutFamily.METRIC_DASHBOARD,
            LayoutFamily.EVIDENCE_BOARD,
            LayoutFamily.TEXTUAL_ARGUMENT,
        ),
        density=DensityLevel.SPACIOUS,
        copy_budget=CopyBudget(
            max_title_chars=24,
            max_message_chars=48,
            max_key_points=0,
            max_body_blocks=0,
        ),
        label="开场大图：一句概念，极少文字",
    ),
)


class PageDirectionService:
    """Derive PageDirection from slide text + archetype + optional rhythm/style."""

    def direct(
        self,
        slide: SlideSpec,
        *,
        page_archetype: PageArchetype | None = None,
        deck_directive: SlideCompositionDirective | None = None,
        style_preset: StylePreset | None = None,
        art_direction: ArtDirection | None = None,
        existing_intent: VisualIntent | None = None,
    ) -> PageDirection:
        blob = _slide_blob(slide)
        archetype = (
            page_archetype
            or getattr(slide, "page_archetype", None)
            or PageArchetype.GENERIC
        )
        if isinstance(archetype, str):
            try:
                archetype = PageArchetype(archetype)
            except ValueError:
                archetype = PageArchetype.GENERIC

        recipe = get_recipe(archetype) if archetype != PageArchetype.GENERIC else None
        rule = _match_situation(blob)
        single_message = _single_message(slide, existing_intent)

        if rule is not None:
            direction = PageDirection(
                single_message=single_message,
                must_show=list(rule.must_show),
                must_hide=list(rule.must_hide),
                composition_bias=list(rule.composition_bias),
                copy_budget=rule.copy_budget.model_copy(),
                preferred_layout_families=list(rule.preferred),
                forbidden_layout_families=list(rule.forbidden),
                density_override=rule.density,
                situation_rule_id=rule.rule_id,
                evidence=[f"situation:{rule.rule_id}:{rule.label}"],
                source="rules",
            )
            return self._merge_with_context(
                direction,
                recipe=recipe,
                deck_directive=deck_directive,
                style_preset=_resolve_preset(style_preset, art_direction),
                director_wins=True,
            )

        # No situation hit — archetype recipe (or generic defaults).
        direction = _from_recipe_or_default(
            single_message=single_message,
            recipe=recipe,
            slide=slide,
        )
        return self._merge_with_context(
            direction,
            recipe=recipe,
            deck_directive=deck_directive,
            style_preset=_resolve_preset(style_preset, art_direction),
            director_wins=False,
        )

    def apply_to_intent(
        self,
        intent: VisualIntent,
        direction: PageDirection,
    ) -> VisualIntent:
        """Write PageDirection onto VisualIntent (families / density / message)."""
        implemented = {item.family for item in get_layout_family_registry().implemented()}
        preferred = [
            fam for fam in direction.preferred_layout_families if fam in implemented
        ]
        if not preferred:
            preferred = list(intent.preferred_layout_families)

        # Drop forbidden from preferred.
        forbidden = set(direction.forbidden_layout_families)
        preferred = [fam for fam in preferred if fam not in forbidden] or preferred

        bias_text = "+".join(b.value for b in direction.composition_bias) or "balanced"
        strategy = (
            f"page_direction:{direction.situation_rule_id or direction.source}; "
            f"bias={bias_text}; "
            f"copy≤{direction.copy_budget.max_key_points}pts/"
            f"{direction.copy_budget.max_message_chars}chars; "
            f"must_show={','.join(direction.must_show[:4])}"
        )
        updates: dict[str, object] = {
            "page_direction": direction,
            "audience_takeaway": direction.single_message,
            "preferred_layout_families": preferred[:3],
            "composition_strategy": strategy,
            "hierarchy": list(direction.must_show) or list(intent.hierarchy),
        }
        if direction.density_override is not None:
            updates["density_level"] = direction.density_override
        if direction.must_hide:
            hide = "、".join(direction.must_hide[:4])
            updates["annotation_strategy"] = (
                f"{intent.annotation_strategy}; 禁止：{hide}".strip("; ")
            )
        return intent.model_copy(update=updates)

    def apply_to_brief(
        self,
        brief: SlideDesignBrief,
        direction: PageDirection,
    ) -> SlideDesignBrief:
        """Mirror Director decisions onto SlideDesignBrief fields."""
        density_map = {
            DensityLevel.SPACIOUS: "low",
            DensityLevel.BALANCED: "medium",
            DensityLevel.COMPACT: "high",
        }
        family = (
            direction.preferred_layout_families[0]
            if direction.preferred_layout_families
            else brief.layout_family
        )
        expected = (
            density_map.get(direction.density_override, brief.expected_density)
            if direction.density_override
            else brief.expected_density
        )
        return brief.model_copy(
            update={
                "central_claim": direction.single_message,
                "layout_family": family,
                "expected_density": expected,
                "required_content": list(
                    dict.fromkeys([*direction.must_show, *brief.required_content])
                ),
                "forbidden_content": list(
                    dict.fromkeys([*direction.must_hide, *brief.forbidden_content])
                ),
                "protection_rules": list(
                    dict.fromkeys(
                        [
                            *brief.protection_rules,
                            *[f"page_direction:{item}" for item in direction.evidence[:3]],
                        ]
                    )
                ),
            }
        )

    def _merge_with_context(
        self,
        direction: PageDirection,
        *,
        recipe: VisualPageRecipe | None,
        deck_directive: SlideCompositionDirective | None,
        style_preset: StylePreset | None,
        director_wins: bool,
    ) -> PageDirection:
        evidence = list(direction.evidence)
        preferred = list(direction.preferred_layout_families)
        forbidden = list(direction.forbidden_layout_families)
        density = direction.density_override
        budget = direction.copy_budget

        if recipe is not None:
            recipe_pref = list(recipe.preferred_layout_families)
            recipe_forbid = list(recipe.forbidden_layout_families)
            if director_wins:
                # Director overrides density/forbidden; merge preferred with Director first.
                preferred = _unique([*preferred, *recipe_pref])
                forbidden = _unique([*forbidden, *recipe_forbid])
                evidence.append(
                    f"merge:director_overrides_archetype:{recipe.archetype.value}"
                )
            else:
                preferred = _unique([*recipe_pref, *preferred])
                forbidden = _unique([*recipe_forbid, *forbidden])
                if density is None:
                    density = recipe.default_density
                evidence.append(f"merge:archetype_base:{recipe.archetype.value}")

        if deck_directive is not None:
            preferred = _unique(
                [*list(deck_directive.preferred_layout_families), *preferred]
            )
            forbidden = _unique(
                [*list(deck_directive.forbidden_layout_families), *forbidden]
            )
            if not director_wins:
                density = deck_directive.target_density
            evidence.append(
                f"merge:deck_directive:{deck_directive.pacing_role.value}"
            )

        if style_preset is not None:
            preferred = _unique(
                [*list(style_preset.preferred_layout_families), *preferred]
            )
            forbidden = _unique(
                [*list(style_preset.forbidden_layout_families), *forbidden]
            )
            # Minimal aesthetics tighten copy further.
            if style_preset.id.value == "architecture_minimal":
                budget = budget.model_copy(
                    update={
                        "max_key_points": max(0, budget.max_key_points - 1),
                        "max_message_chars": min(budget.max_message_chars, 64),
                        "max_body_blocks": min(budget.max_body_blocks, 1),
                    }
                )
                evidence.append("style_preset:architecture_minimal:tighter_copy")
            else:
                evidence.append(f"style_preset:{style_preset.id.value}")

        # Preferred must not include forbidden.
        preferred = [fam for fam in preferred if fam not in set(forbidden)]
        if not preferred:
            preferred = [LayoutFamily.HYBRID_CANVAS]

        return direction.model_copy(
            update={
                "preferred_layout_families": preferred[:3],
                "forbidden_layout_families": forbidden,
                "density_override": density,
                "copy_budget": budget,
                "evidence": evidence,
            }
        )


def apply_page_direction_to_intent(
    intent: VisualIntent,
    direction: PageDirection,
) -> VisualIntent:
    """Module-level helper for pipelines / tests."""
    return PageDirectionService().apply_to_intent(intent, direction)


def _resolve_preset(
    style_preset: StylePreset | None,
    art_direction: ArtDirection | None,
) -> StylePreset | None:
    if style_preset is not None:
        return style_preset
    if art_direction is None or not art_direction.style_preset_id:
        return None
    try:
        return get_style_preset(art_direction.style_preset_id)
    except KeyError:
        return None


def _match_situation(blob: str) -> _SituationRule | None:
    for rule in _SITUATION_RULES:
        if any(pattern.search(blob) for pattern in rule.patterns):
            return rule
    return None


def _slide_blob(slide: SlideSpec) -> str:
    parts = [
        slide.title or "",
        slide.message or "",
        " ".join(slide.key_points or []),
    ]
    return "\n".join(parts)


def _single_message(
    slide: SlideSpec,
    existing_intent: VisualIntent | None,
) -> str:
    raw = (slide.message or "").strip()
    if not raw and existing_intent is not None:
        raw = (existing_intent.audience_takeaway or "").strip()
    if not raw:
        raw = (slide.title or "本页传达一个核心判断").strip()
    # First sentence only.
    for sep in ("。", "！", "？", ".", "!", "?"):
        if sep in raw:
            raw = raw.split(sep, 1)[0].strip()
            break
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:500] or "本页只讲一个核心矛盾。"


def _from_recipe_or_default(
    *,
    single_message: str,
    recipe: VisualPageRecipe | None,
    slide: SlideSpec,
) -> PageDirection:
    if recipe is None:
        return PageDirection(
            single_message=single_message,
            must_show=["title", "primary_visual", "conclusion"],
            must_hide=["decorative_noise"],
            composition_bias=[CompositionBias.TEXT_LEAD],
            copy_budget=CopyBudget(
                max_title_chars=36,
                max_message_chars=min(120, max(40, len(single_message) + 20)),
                max_key_points=min(4, len(slide.key_points or []) or 3),
                max_body_blocks=2,
            ),
            preferred_layout_families=[LayoutFamily.HYBRID_CANVAS],
            forbidden_layout_families=[],
            density_override=DensityLevel.BALANCED,
            evidence=["fallback:generic_balanced"],
            source="rules",
        )
    bias = _bias_from_recipe(recipe)
    return PageDirection(
        single_message=single_message,
        must_show=[zone.role for zone in recipe.composition_zones[:4]],
        must_hide=["layout_family_conflict"],
        composition_bias=bias,
        copy_budget=CopyBudget(
            max_title_chars=32,
            max_message_chars=100,
            max_key_points=3 if recipe.default_density != DensityLevel.SPACIOUS else 1,
            max_body_blocks=1,
        ),
        preferred_layout_families=list(recipe.preferred_layout_families),
        forbidden_layout_families=list(recipe.forbidden_layout_families),
        density_override=recipe.default_density,
        evidence=[f"archetype:{recipe.archetype.value}"],
        source="archetype",
    )


def _bias_from_recipe(recipe: VisualPageRecipe) -> list[CompositionBias]:
    family = (
        recipe.preferred_layout_families[0]
        if recipe.preferred_layout_families
        else LayoutFamily.HYBRID_CANVAS
    )
    mapping: dict[LayoutFamily, list[CompositionBias]] = {
        LayoutFamily.HERO: [CompositionBias.HERO_FULL],
        LayoutFamily.EVIDENCE_BOARD: [
            CompositionBias.EVIDENCE_GRID,
            CompositionBias.CONCLUSION_BAR,
        ],
        LayoutFamily.DRAWING_FOCUS: [CompositionBias.DRAWING_DOMINANT],
        LayoutFamily.ANALYTICAL_DIAGRAM: [CompositionBias.DIAGRAM_CENTER],
        LayoutFamily.STRATEGY_CARDS: [CompositionBias.STRATEGY_CARDS],
        LayoutFamily.COMPARATIVE_MATRIX: [CompositionBias.BEFORE_AFTER],
        LayoutFamily.TEXTUAL_ARGUMENT: [CompositionBias.TEXT_LEAD],
        LayoutFamily.HYBRID_CANVAS: [
            CompositionBias.PHOTO_LEFT,
            CompositionBias.CONCLUSION_BAR,
        ],
    }
    return mapping.get(family, [CompositionBias.TEXT_LEAD])


def _unique(items: list[LayoutFamily]) -> list[LayoutFamily]:
    seen: set[LayoutFamily] = set()
    out: list[LayoutFamily] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
