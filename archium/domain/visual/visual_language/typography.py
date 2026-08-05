"""Typography recipes + role catalog — title as visual rhetoric.

Recipes describe page-level title intent (giant bilingual, architectural…).
Roles describe *which kind of text* (HERO_TITLE, INDEX, CAPTION…) with
executable size / tracking / case / opacity / position bias.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class TypographyRecipeId(StrEnum):
    DEFAULT = "default"
    ARCHITECTURAL_TITLE = "architectural_title"
    GIANT_BILINGUAL = "giant_bilingual"
    SECTION_INDEX = "section_index"


class TypographyRole(StrEnum):
    """Semantic text roles — not raw font sizes."""

    HERO_TITLE = "hero_title"
    SECTION_TITLE = "section_title"
    DRAWING_LABEL = "drawing_label"
    TECH_NOTE = "tech_note"
    CAPTION = "caption"
    QUOTE = "quote"
    INDEX = "index"


class TitleScale(StrEnum):
    NORMAL = "normal"
    LARGE = "large"
    GIANT = "giant"


class Tracking(StrEnum):
    NORMAL = "normal"
    WIDE = "wide"
    TIGHT = "tight"


class TitleCase(StrEnum):
    AS_IS = "as_is"
    UPPERCASE = "uppercase"


class TitleDecoration(StrEnum):
    NONE = "none"
    THIN_LINE = "thin_line"


class TypographyPosition(StrEnum):
    """Relative placement bias (absolute coords still come from layout)."""

    INHERIT = "inherit"
    EDGE = "edge"
    ABOVE_TITLE = "above_title"
    BELOW_TITLE = "below_title"
    INLINE = "inline"


_TRACKING_EM: dict[Tracking, float] = {
    Tracking.TIGHT: -0.02,
    Tracking.NORMAL: 0.0,
    Tracking.WIDE: 0.08,
}


class TypographyRoleSpec(DomainModel):
    """Executable attributes for one TypographyRole."""

    role: TypographyRole
    font_size_pt: float = Field(ge=8, le=120)
    tracking: Tracking = Tracking.NORMAL
    case: TitleCase = TitleCase.AS_IS
    opacity: float = Field(default=1.0, ge=0.3, le=1.0)
    letter_spacing_em: float | None = Field(default=None, ge=-0.1, le=0.5)
    style_token: str = "body"
    position: TypographyPosition = TypographyPosition.INHERIT
    font_weight: int = Field(default=400, ge=300, le=900)

    def resolved_letter_spacing(self) -> float:
        if self.letter_spacing_em is not None:
            return self.letter_spacing_em
        return _TRACKING_EM[self.tracking]

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "font_size_pt": self.font_size_pt,
            "tracking": self.tracking.value,
            "case": self.case.value,
            "opacity": self.opacity,
            "letter_spacing_em": self.resolved_letter_spacing(),
            "style_token": self.style_token,
            "position": self.position.value,
            "font_weight": self.font_weight,
        }


# Default office catalog — competition / institute presentation norms.
ROLE_CATALOG: dict[TypographyRole, TypographyRoleSpec] = {
    TypographyRole.HERO_TITLE: TypographyRoleSpec(
        role=TypographyRole.HERO_TITLE,
        font_size_pt=36,
        tracking=Tracking.WIDE,
        case=TitleCase.AS_IS,
        opacity=0.95,
        letter_spacing_em=0.06,
        style_token="display",
        position=TypographyPosition.EDGE,
        font_weight=700,
    ),
    TypographyRole.SECTION_TITLE: TypographyRoleSpec(
        role=TypographyRole.SECTION_TITLE,
        font_size_pt=26,
        tracking=Tracking.WIDE,
        case=TitleCase.AS_IS,
        opacity=1.0,
        letter_spacing_em=0.04,
        style_token="title",
        position=TypographyPosition.EDGE,
        font_weight=700,
    ),
    TypographyRole.DRAWING_LABEL: TypographyRoleSpec(
        role=TypographyRole.DRAWING_LABEL,
        font_size_pt=11,
        tracking=Tracking.NORMAL,
        case=TitleCase.AS_IS,
        opacity=0.9,
        letter_spacing_em=0.02,
        style_token="caption",
        position=TypographyPosition.INLINE,
        font_weight=500,
    ),
    TypographyRole.TECH_NOTE: TypographyRoleSpec(
        role=TypographyRole.TECH_NOTE,
        font_size_pt=12,
        tracking=Tracking.WIDE,
        case=TitleCase.UPPERCASE,
        opacity=0.85,
        letter_spacing_em=0.12,
        style_token="caption",
        position=TypographyPosition.BELOW_TITLE,
        font_weight=400,
    ),
    TypographyRole.CAPTION: TypographyRoleSpec(
        role=TypographyRole.CAPTION,
        font_size_pt=10,
        tracking=Tracking.NORMAL,
        case=TitleCase.AS_IS,
        opacity=0.8,
        letter_spacing_em=0.02,
        style_token="caption",
        position=TypographyPosition.INLINE,
        font_weight=400,
    ),
    TypographyRole.QUOTE: TypographyRoleSpec(
        role=TypographyRole.QUOTE,
        font_size_pt=20,
        tracking=Tracking.NORMAL,
        case=TitleCase.AS_IS,
        opacity=0.92,
        letter_spacing_em=0.0,
        style_token="title",
        position=TypographyPosition.INHERIT,
        font_weight=400,
    ),
    TypographyRole.INDEX: TypographyRoleSpec(
        role=TypographyRole.INDEX,
        font_size_pt=11,
        tracking=Tracking.WIDE,
        case=TitleCase.UPPERCASE,
        opacity=0.75,
        letter_spacing_em=0.14,
        style_token="caption",
        position=TypographyPosition.ABOVE_TITLE,
        font_weight=500,
    ),
}


_RECIPE_PRIMARY_ROLE: dict[TypographyRecipeId, TypographyRole] = {
    TypographyRecipeId.GIANT_BILINGUAL: TypographyRole.HERO_TITLE,
    TypographyRecipeId.ARCHITECTURAL_TITLE: TypographyRole.SECTION_TITLE,
    TypographyRecipeId.SECTION_INDEX: TypographyRole.INDEX,
    TypographyRecipeId.DEFAULT: TypographyRole.SECTION_TITLE,
}


def role_spec(role: TypographyRole) -> TypographyRoleSpec:
    """Return catalog default for a role (copy-safe via model_copy)."""
    return ROLE_CATALOG[role].model_copy()


def primary_role_for_recipe(recipe: TypographyRecipeId) -> TypographyRole:
    return _RECIPE_PRIMARY_ROLE.get(recipe, TypographyRole.SECTION_TITLE)


class TypographyRecipe(DomainModel):
    """Executable title / bilingual typography intent (no absolute coords)."""

    recipe: TypographyRecipeId = TypographyRecipeId.DEFAULT
    primary_role: TypographyRole = TypographyRole.SECTION_TITLE
    scale: TitleScale = TitleScale.NORMAL
    tracking: Tracking = Tracking.NORMAL
    case: TitleCase = TitleCase.AS_IS
    decoration: TitleDecoration = TitleDecoration.NONE
    bilingual: bool = False
    english_label: str | None = Field(default=None, max_length=120)
    # Resolved pt hints for layout bridge (DesignSystem may clamp).
    title_font_size_pt: float | None = Field(default=None, ge=12, le=120)
    english_font_size_pt: float | None = Field(default=None, ge=8, le=48)
    letter_spacing_em: float = Field(default=0.0, ge=-0.1, le=0.5)
    opacity: float = Field(default=1.0, ge=0.3, le=1.0)
    # Optional per-role overrides (role value → partial size/opacity tweaks).
    role_overrides: dict[str, float] = Field(
        default_factory=dict,
        description="Optional font_size_pt overrides keyed by TypographyRole value.",
    )

    def resolve_role(self, role: TypographyRole) -> TypographyRoleSpec:
        """Catalog role merged with recipe-level title overrides when primary."""
        base = role_spec(role)
        updates: dict[str, object] = {}
        override_size = self.role_overrides.get(role.value)
        if override_size is not None:
            updates["font_size_pt"] = override_size
        if role == self.primary_role:
            if self.title_font_size_pt is not None:
                updates["font_size_pt"] = self.title_font_size_pt
            updates["tracking"] = self.tracking
            updates["case"] = self.case
            updates["opacity"] = self.opacity
            updates["letter_spacing_em"] = self.letter_spacing_em
            if self.scale == TitleScale.GIANT:
                updates["style_token"] = "display"
                updates["font_weight"] = max(base.font_weight, 600)
            elif self.scale == TitleScale.LARGE:
                updates["font_weight"] = max(base.font_weight, 600)
        if role == TypographyRole.TECH_NOTE and self.english_font_size_pt is not None:
            updates["font_size_pt"] = self.english_font_size_pt
        return base.model_copy(update=updates) if updates else base

    def as_dict(self) -> dict[str, object]:
        return {
            "recipe": self.recipe.value,
            "primary_role": self.primary_role.value,
            "scale": self.scale.value,
            "tracking": self.tracking.value,
            "case": self.case.value,
            "decoration": self.decoration.value,
            "bilingual": self.bilingual,
            "english_label": self.english_label,
            "title_font_size_pt": self.title_font_size_pt,
            "english_font_size_pt": self.english_font_size_pt,
            "letter_spacing_em": self.letter_spacing_em,
            "opacity": self.opacity,
            "roles": {
                role.value: self.resolve_role(role).as_dict()
                for role in (
                    self.primary_role,
                    TypographyRole.TECH_NOTE,
                    TypographyRole.INDEX,
                    TypographyRole.CAPTION,
                )
            },
        }
