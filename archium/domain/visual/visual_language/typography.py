"""Typography recipes — title as visual rhetoric (not just Arial 32pt)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class TypographyRecipeId(StrEnum):
    DEFAULT = "default"
    ARCHITECTURAL_TITLE = "architectural_title"
    GIANT_BILINGUAL = "giant_bilingual"
    SECTION_INDEX = "section_index"


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


class TypographyRecipe(DomainModel):
    """Executable title / bilingual typography intent (no absolute coords)."""

    recipe: TypographyRecipeId = TypographyRecipeId.DEFAULT
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

    def as_dict(self) -> dict[str, object]:
        return {
            "recipe": self.recipe.value,
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
        }
