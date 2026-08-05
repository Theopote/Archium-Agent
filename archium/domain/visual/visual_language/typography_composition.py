"""TypographyComposition — executable multi-run text design (VQ-001).

Distinct from ``TypographySystem`` tokens (hierarchy) and ``TypographyRecipe``
(page-level intent). This model answers: which spans get which scale/weight/
color so a title is *composed*, not merely styled as one box.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class TypographyPageKind(StrEnum):
    """Five Phase-1 page kinds that must escape default-template typography."""

    COVER = "cover"
    SECTION = "section"
    THESIS = "thesis"
    METRIC = "metric"
    CLOSING = "closing"
    DEFAULT = "default"


class TypographyArrangement(StrEnum):
    INLINE = "inline"
    STACKED = "stacked"
    METRIC_STACK = "metric_stack"


class TypographyRunRole(StrEnum):
    HERO_WORD = "hero_word"
    SUPPORT_WORD = "support_word"
    CONNECTOR = "connector"
    METRIC_VALUE = "metric_value"
    METRIC_UNIT = "metric_unit"
    LABEL = "label"
    GHOST = "ghost"


class TypographyRunSpec(DomainModel):
    """One designed span inside a composition (maps to RenderScene TextRun)."""

    text: str
    semantic_role: TypographyRunRole = TypographyRunRole.SUPPORT_WORD
    size_scale: float = Field(default=1.0, gt=0.2, le=8.0)
    font_weight: int | None = Field(default=None, ge=100, le=900)
    color_token: str | None = Field(
        default=None,
        description="DesignSystem color token name (accent, muted_text, …).",
    )
    tracking_em: float | None = Field(default=None, ge=-0.1, le=0.5)
    opacity: float | None = Field(default=None, ge=0.05, le=1.0)
    uppercase: bool = False
    break_after: bool = False


class TypographyComposition(DomainModel):
    """Page-aware typography composition — no absolute coordinates."""

    page_kind: TypographyPageKind = TypographyPageKind.DEFAULT
    arrangement: TypographyArrangement = TypographyArrangement.INLINE
    runs: list[TypographyRunSpec] = Field(default_factory=list)
    letter_spacing_em: float = Field(default=0.0, ge=-0.1, le=0.5)
    base_size_pt: float | None = Field(default=None, ge=8, le=120)
    # Oversized background word (separate TextNode at compile time).
    ghost_text: str | None = Field(default=None, max_length=12)
    ghost_size_scale: float = Field(default=5.0, gt=1.0, le=12.0)
    ghost_opacity: float = Field(default=0.07, ge=0.03, le=0.25)

    def plain_text(self) -> str:
        parts: list[str] = []
        for run in self.runs:
            parts.append(run.text)
            if run.break_after:
                parts.append("\n")
        return "".join(parts)
