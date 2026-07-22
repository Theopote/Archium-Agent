"""Map ReferenceStyle layout cues (+ ArtDirection layout hints) to LayoutPlan preferences.

Does **not** invent geometry. It only ranks LayoutFamily / variant candidates so
style language (full-bleed hero, photo grids, drawing focus, …) influences
which plans are generated and selected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from archium.domain.reference_style import ReferenceStyleProfile, StyleLayoutCue
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.enums import LayoutFamily

# (compiled pattern, family, preferred variant or None)
_LAYOUT_RULES: tuple[tuple[re.Pattern[str], LayoutFamily, str | None], ...] = (
    (
        re.compile(
            r"full[_\s-]?bleed|fullbleed|全出血|出血|大图封面|封面大图|hero\s*bleed",
            re.I,
        ),
        LayoutFamily.HERO,
        "full_bleed",
    ),
    (
        re.compile(r"\bsplit\b|对开|左右分栏|半图半文|image[_\s-]?text", re.I),
        LayoutFamily.HERO,
        "split",
    ),
    (
        re.compile(r"\boverlay\b|叠字|图上文字|文字压图", re.I),
        LayoutFamily.HERO,
        "overlay",
    ),
    (
        re.compile(
            r"photo[_\s-]?grid|numbered[_\s-]?grid|证据板|多图|照片网格|image\s*grid",
            re.I,
        ),
        LayoutFamily.EVIDENCE_BOARD,
        "photo_grid",
    ),
    (
        re.compile(r"journey|游线|路径照片|numbered\s*evidence", re.I),
        LayoutFamily.EVIDENCE_BOARD,
        "journey_with_photos",
    ),
    (
        re.compile(
            r"drawing|图纸|平面|总平面|立面|剖面|canvas|图面主导|technical\s*drawing",
            re.I,
        ),
        LayoutFamily.DRAWING_FOCUS,
        "drawing_with_metrics",
    ),
    (
        re.compile(r"annotation|标注|callout|带注记", re.I),
        LayoutFamily.DRAWING_FOCUS,
        "drawing_with_annotations",
    ),
    (
        re.compile(r"metric|指标|dashboard|kpi|数据看板|数字板", re.I),
        LayoutFamily.METRIC_DASHBOARD,
        None,
    ),
    (
        re.compile(r"process|流程|timeline|分期|阶段|叙事轴", re.I),
        LayoutFamily.PROCESS_NARRATIVE,
        None,
    ),
    (
        re.compile(
            r"compar|对比|before[_\s-]?after|矩阵|对照|comparative",
            re.I,
        ),
        LayoutFamily.COMPARATIVE_MATRIX,
        None,
    ),
    (
        re.compile(r"diagram|分析图|示意|analytical", re.I),
        LayoutFamily.ANALYTICAL_DIAGRAM,
        None,
    ),
    (
        re.compile(r"strategy\s*card|策略卡|卡片组|card\s*grid", re.I),
        LayoutFamily.STRATEGY_CARDS,
        None,
    ),
    (
        re.compile(r"text(?:ual)?|论证|文字主导|lead[_\s-]?and[_\s-]?points|正文", re.I),
        LayoutFamily.TEXTUAL_ARGUMENT,
        "lead_and_points",
    ),
    (
        re.compile(r"hybrid|混合|图文混排|asymmetric|非对称", re.I),
        LayoutFamily.HYBRID_CANVAS,
        None,
    ),
    (
        re.compile(r"\bhero\b|主视觉|大图|cover\s*image", re.I),
        LayoutFamily.HERO,
        None,
    ),
    (
        re.compile(r"evidence|证据", re.I),
        LayoutFamily.EVIDENCE_BOARD,
        None,
    ),
)


@dataclass(frozen=True)
class LayoutStylePreference:
    """Ranked layout-family / variant hints from style artifacts."""

    preferred_families: tuple[LayoutFamily, ...] = ()
    # Ordered (family, variant) pairs — variant may be empty string for family-only.
    preferred_variants: tuple[tuple[LayoutFamily, str], ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.preferred_families and not self.preferred_variants

    def family_rank(self, family: LayoutFamily) -> int | None:
        try:
            return self.preferred_families.index(family)
        except ValueError:
            return None

    def variant_rank(self, family: LayoutFamily, variant: str) -> int | None:
        key = (family, variant)
        try:
            return self.preferred_variants.index(key)
        except ValueError:
            return None

    def selection_bonus(self, family: LayoutFamily, variant: str) -> float:
        """Small score bonus used by candidate selection (lower sort key wins)."""
        bonus = 0.0
        rank = self.family_rank(family)
        if rank == 0:
            bonus += 0.07
        elif rank is not None:
            bonus += max(0.02, 0.05 - 0.01 * rank)
        v_rank = self.variant_rank(family, variant)
        if v_rank == 0:
            bonus += 0.05
        elif v_rank is not None:
            bonus += 0.02
        return bonus


def derive_layout_style_preference(
    *,
    reference_style: ReferenceStyleProfile | None = None,
    art_direction: ArtDirection | None = None,
) -> LayoutStylePreference:
    """Derive ranked layout preferences from style cues and art-direction text."""
    if reference_style is None and art_direction is None:
        return LayoutStylePreference()

    family_scores: dict[LayoutFamily, float] = {}
    variant_scores: dict[tuple[LayoutFamily, str], float] = {}
    notes: list[str] = []

    if reference_style is not None:
        for index, cue in enumerate(reference_style.layout_cues):
            weight = 1.0 - min(index, 5) * 0.05
            hits = _match_text(_cue_text(cue), weight=weight)
            if not hits:
                notes.append(f"layout_style:skipped_cue:{cue.id}:unmatched")
                continue
            for family, variant, score in hits:
                family_scores[family] = family_scores.get(family, 0.0) + score
                if variant:
                    key = (family, variant)
                    variant_scores[key] = variant_scores.get(key, 0.0) + score
                notes.append(
                    f"layout_style:cue:{cue.id}->{family.value}"
                    + (f"/{variant}" if variant else "")
                )

        # Density / pacing cues without explicit layout pattern.
        density = (reference_style.pacing_density or "").lower()
        if density in {"dense", "compact", "密集"}:
            family_scores[LayoutFamily.METRIC_DASHBOARD] = (
                family_scores.get(LayoutFamily.METRIC_DASHBOARD, 0.0) + 0.25
            )
            family_scores[LayoutFamily.EVIDENCE_BOARD] = (
                family_scores.get(LayoutFamily.EVIDENCE_BOARD, 0.0) + 0.15
            )
            notes.append("layout_style:pacing_density:dense")
        elif density in {"spacious", "loose", "疏朗", "留白"}:
            family_scores[LayoutFamily.HERO] = family_scores.get(LayoutFamily.HERO, 0.0) + 0.2
            family_scores[LayoutFamily.TEXTUAL_ARGUMENT] = (
                family_scores.get(LayoutFamily.TEXTUAL_ARGUMENT, 0.0) + 0.15
            )
            notes.append("layout_style:pacing_density:spacious")

    if art_direction is not None:
        art_blob = " ".join(
            [
                art_direction.grid_strategy or "",
                art_direction.image_strategy or "",
                art_direction.drawing_strategy or "",
                art_direction.cover_strategy or "",
                art_direction.content_strategy or "",
                art_direction.section_strategy or "",
                art_direction.diagram_strategy or "",
            ]
        )
        hits = _match_text(art_blob, weight=0.7)
        for family, variant, score in hits:
            family_scores[family] = family_scores.get(family, 0.0) + score
            if variant:
                key = (family, variant)
                variant_scores[key] = variant_scores.get(key, 0.0) + score
        if hits:
            notes.append(
                "layout_style:art_direction:"
                + ",".join(sorted({family.value for family, _, _ in hits}))
            )

    if not family_scores and not variant_scores:
        notes.append("layout_style:no_resolvable_cues")
        return LayoutStylePreference(notes=tuple(notes))

    preferred_families = tuple(
        family
        for family, _score in sorted(
            family_scores.items(),
            key=lambda item: (-item[1], item[0].value),
        )
    )
    preferred_variants = tuple(
        key
        for key, _score in sorted(
            variant_scores.items(),
            key=lambda item: (-item[1], item[0][0].value, item[0][1]),
        )
    )
    notes.append(
        "layout_style:preferred_families="
        + ",".join(family.value for family in preferred_families[:5])
    )
    return LayoutStylePreference(
        preferred_families=preferred_families,
        preferred_variants=preferred_variants,
        notes=tuple(notes),
    )


def _cue_text(cue: StyleLayoutCue) -> str:
    return f"{cue.pattern} {cue.description}".strip()


def _match_text(
    text: str,
    *,
    weight: float = 1.0,
) -> list[tuple[LayoutFamily, str | None, float]]:
    if not text or not text.strip():
        return []
    hits: list[tuple[LayoutFamily, str | None, float]] = []
    for pattern, family, variant in _LAYOUT_RULES:
        if pattern.search(text):
            # More specific rules (with variant) slightly outrank family-only.
            score = weight * (1.1 if variant else 1.0)
            hits.append((family, variant, score))
    return hits


def merge_preferred_families(
    *groups: list[LayoutFamily] | tuple[LayoutFamily, ...] | None,
) -> list[LayoutFamily]:
    """Stable de-duplicated merge; earlier groups win rank."""
    merged: list[LayoutFamily] = []
    seen: set[LayoutFamily] = set()
    for group in groups:
        if not group:
            continue
        for family in group:
            if family in seen:
                continue
            seen.add(family)
            merged.append(family)
    return merged
