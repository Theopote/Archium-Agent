"""LayoutFamily registry — content affinities, variants, required roles."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.enums import LayoutElementRole, LayoutFamily, VisualContentType

_DRAWING_TYPES = {
    VisualContentType.SITE_PLAN,
    VisualContentType.FLOOR_PLAN,
    VisualContentType.SECTION,
    VisualContentType.ELEVATION,
}


@dataclass(frozen=True)
class LayoutFamilyDefinition:
    family: LayoutFamily
    supported_content_types: frozenset[VisualContentType]
    min_assets: int
    max_assets: int
    supported_variants: tuple[str, ...]
    default_variant: str
    required_roles: tuple[LayoutElementRole, ...]
    optional_roles: tuple[LayoutElementRole, ...] = ()
    implemented: bool = True
    description: str = ""


def _def(
    family: LayoutFamily,
    *,
    content: set[VisualContentType],
    min_assets: int,
    max_assets: int,
    variants: tuple[str, ...],
    default: str,
    required: tuple[LayoutElementRole, ...],
    optional: tuple[LayoutElementRole, ...] = (),
    implemented: bool = True,
    description: str = "",
) -> LayoutFamilyDefinition:
    return LayoutFamilyDefinition(
        family=family,
        supported_content_types=frozenset(content),
        min_assets=min_assets,
        max_assets=max_assets,
        supported_variants=variants,
        default_variant=default,
        required_roles=required,
        optional_roles=optional,
        implemented=implemented,
        description=description,
    )


_REGISTRY: dict[LayoutFamily, LayoutFamilyDefinition] = {
    LayoutFamily.HERO: _def(
        LayoutFamily.HERO,
        content={
            VisualContentType.HERO_IMAGE,
            VisualContentType.PHOTO_EVIDENCE,
            VisualContentType.MIXED,
        },
        min_assets=1,
        max_assets=2,
        variants=("full_bleed", "split", "overlay"),
        default="split",
        required=(
            LayoutElementRole.TITLE,
            LayoutElementRole.HERO_VISUAL,
        ),
        optional=(
            LayoutElementRole.SUBTITLE,
            LayoutElementRole.LEAD_STATEMENT,
            LayoutElementRole.SOURCE,
            LayoutElementRole.CAPTION,
        ),
        description="Dominant image with restrained supporting text.",
    ),
    LayoutFamily.EVIDENCE_BOARD: _def(
        LayoutFamily.EVIDENCE_BOARD,
        content={VisualContentType.PHOTO_EVIDENCE, VisualContentType.MIXED},
        min_assets=2,
        max_assets=8,
        variants=("photo_grid", "numbered_grid", "journey_with_photos"),
        default="numbered_grid",
        required=(
            LayoutElementRole.TITLE,
            LayoutElementRole.SUPPORTING_VISUAL,
            LayoutElementRole.LEAD_STATEMENT,
        ),
        optional=(
            LayoutElementRole.CAPTION,
            LayoutElementRole.ANNOTATION,
            LayoutElementRole.SOURCE,
            LayoutElementRole.BODY_TEXT,
        ),
        description="Multiple evidence photos with numbered correspondence.",
    ),
    LayoutFamily.DRAWING_FOCUS: _def(
        LayoutFamily.DRAWING_FOCUS,
        content=_DRAWING_TYPES | {VisualContentType.MIXED},
        min_assets=1,
        max_assets=4,
        variants=(
            "full_canvas",
            "drawing_with_metrics",
            "drawing_with_details",
            "drawing_with_annotations",
        ),
        default="drawing_with_metrics",
        required=(
            LayoutElementRole.TITLE,
            LayoutElementRole.HERO_VISUAL,
            LayoutElementRole.CAPTION,
            LayoutElementRole.SOURCE,
        ),
        optional=(
            LayoutElementRole.METRIC,
            LayoutElementRole.BODY_TEXT,
            LayoutElementRole.ANNOTATION,
        ),
        description="Technical drawing as hero; contain fit; no decorative crop.",
    ),
    LayoutFamily.COMPARATIVE_MATRIX: _def(
        LayoutFamily.COMPARATIVE_MATRIX,
        content={VisualContentType.COMPARISON, VisualContentType.MIXED},
        min_assets=2,
        max_assets=6,
        variants=("equal_columns", "matrix_with_insight", "before_after"),
        default="matrix_with_insight",
        required=(
            LayoutElementRole.TITLE,
            LayoutElementRole.SUPPORTING_VISUAL,
            LayoutElementRole.BODY_TEXT,
        ),
        optional=(
            LayoutElementRole.LEAD_STATEMENT,
            LayoutElementRole.CAPTION,
            LayoutElementRole.SOURCE,
        ),
        description="Equal-weight case comparison with aligned dimensions.",
    ),
    LayoutFamily.PROCESS_NARRATIVE: _def(
        LayoutFamily.PROCESS_NARRATIVE,
        content={VisualContentType.PROCESS, VisualContentType.MIXED},
        min_assets=0,
        max_assets=6,
        variants=("timeline", "steps_horizontal"),
        default="timeline",
        required=(LayoutElementRole.TITLE, LayoutElementRole.BODY_TEXT),
        optional=(LayoutElementRole.SUPPORTING_VISUAL, LayoutElementRole.SOURCE),
        implemented=False,
        description="Process / timeline narrative (definition only in v1).",
    ),
    LayoutFamily.ANALYTICAL_DIAGRAM: _def(
        LayoutFamily.ANALYTICAL_DIAGRAM,
        content={VisualContentType.ANALYTICAL_DIAGRAM, VisualContentType.MIXED},
        min_assets=1,
        max_assets=3,
        variants=("diagram_focus", "diagram_with_callouts"),
        default="diagram_focus",
        required=(LayoutElementRole.TITLE, LayoutElementRole.HERO_VISUAL),
        optional=(LayoutElementRole.ANNOTATION, LayoutElementRole.SOURCE),
        implemented=False,
        description="Analytical diagram focus (definition only in v1).",
    ),
    LayoutFamily.METRIC_DASHBOARD: _def(
        LayoutFamily.METRIC_DASHBOARD,
        content={VisualContentType.METRICS, VisualContentType.MIXED},
        min_assets=0,
        max_assets=2,
        variants=("metric_cards", "metric_with_chart"),
        default="metric_cards",
        required=(LayoutElementRole.TITLE, LayoutElementRole.METRIC),
        optional=(LayoutElementRole.BODY_TEXT, LayoutElementRole.SOURCE),
        implemented=False,
        description="Metric dashboard (definition only in v1).",
    ),
    LayoutFamily.STRATEGY_CARDS: _def(
        LayoutFamily.STRATEGY_CARDS,
        content={VisualContentType.TEXT_ARGUMENT, VisualContentType.MIXED},
        min_assets=0,
        max_assets=3,
        variants=("three_cards", "four_cards", "cards_with_lead"),
        default="three_cards",
        required=(LayoutElementRole.TITLE, LayoutElementRole.BODY_TEXT),
        optional=(
            LayoutElementRole.LEAD_STATEMENT,
            LayoutElementRole.SUPPORTING_VISUAL,
            LayoutElementRole.SOURCE,
        ),
        description="Strategy / principle cards with clear hierarchy.",
    ),
    LayoutFamily.TEXTUAL_ARGUMENT: _def(
        LayoutFamily.TEXTUAL_ARGUMENT,
        content={VisualContentType.TEXT_ARGUMENT, VisualContentType.MIXED},
        min_assets=0,
        max_assets=1,
        variants=("lead_and_points", "quote_argument", "two_column_text"),
        default="lead_and_points",
        required=(
            LayoutElementRole.TITLE,
            LayoutElementRole.LEAD_STATEMENT,
            LayoutElementRole.BODY_TEXT,
        ),
        optional=(LayoutElementRole.SOURCE, LayoutElementRole.SUPPORTING_VISUAL),
        description="Text-led argument with controlled density.",
    ),
    LayoutFamily.HYBRID_CANVAS: _def(
        LayoutFamily.HYBRID_CANVAS,
        content={VisualContentType.MIXED},
        min_assets=1,
        max_assets=6,
        variants=("freeform",),
        default="freeform",
        required=(LayoutElementRole.TITLE,),
        optional=tuple(LayoutElementRole),
        implemented=False,
        description="Hybrid canvas (definition only in v1).",
    ),
}


class LayoutFamilyRegistry:
    """Register and query LayoutFamily definitions."""

    def __init__(self, definitions: dict[LayoutFamily, LayoutFamilyDefinition] | None = None) -> None:
        self._definitions = dict(definitions or _REGISTRY)

    def get(self, family: LayoutFamily) -> LayoutFamilyDefinition:
        try:
            return self._definitions[family]
        except KeyError as exc:
            raise KeyError(f"unknown layout family: {family}") from exc

    def all(self) -> list[LayoutFamilyDefinition]:
        return list(self._definitions.values())

    def implemented(self) -> list[LayoutFamilyDefinition]:
        return [item for item in self._definitions.values() if item.implemented]

    def candidates_for(
        self,
        content_type: VisualContentType,
        *,
        asset_count: int,
        preferred: list[LayoutFamily] | None = None,
        implemented_only: bool = True,
    ) -> list[LayoutFamilyDefinition]:
        """Return ranked family definitions compatible with content + asset count."""
        pool = self.implemented() if implemented_only else self.all()
        compatible = [
            item
            for item in pool
            if content_type in item.supported_content_types
            and item.min_assets <= asset_count <= item.max_assets
        ]
        if not compatible:
            # Soft fallback: ignore asset bounds but keep content affinity.
            compatible = [
                item
                for item in pool
                if content_type in item.supported_content_types
            ]
        if not compatible:
            compatible = list(pool)

        preferred = preferred or []
        preferred_set = set(preferred)

        def sort_key(item: LayoutFamilyDefinition) -> tuple[int, int, str]:
            pref_rank = preferred.index(item.family) if item.family in preferred_set else 99
            asset_fit = 0 if item.min_assets <= asset_count <= item.max_assets else 1
            return (pref_rank, asset_fit, item.family.value)

        return sorted(compatible, key=sort_key)

    def resolve_variant(self, family: LayoutFamily, variant: str | None) -> str:
        definition = self.get(family)
        if variant and variant in definition.supported_variants:
            return variant
        return definition.default_variant


_DEFAULT_REGISTRY = LayoutFamilyRegistry()


def get_layout_family_registry() -> LayoutFamilyRegistry:
    return _DEFAULT_REGISTRY
