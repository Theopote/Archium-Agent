"""Deck-level Visual QA — cross-page consistency (read-only).

Distinct from per-page Layout Validation and per-page Visual Critic.
Never auto-repairs layouts and never blocks formal PPTX export.
"""

from __future__ import annotations

from pydantic import Field, computed_field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutIssueSeverity
from archium.domain.visual.severity import layout_is_gate_blocker

DECK_REPEATED_LAYOUT_FAMILY = "DECK.REPEATED_LAYOUT_FAMILY"
DECK_FOOTER_INCONSISTENT = "DECK.FOOTER_INCONSISTENT"
DECK_TYPOGRAPHY_INCONSISTENT = "DECK.TYPOGRAPHY_INCONSISTENT"
DECK_WEAK_SECTION_TRANSITION = "DECK.WEAK_SECTION_TRANSITION"
DECK_IMAGE_SCALE_INCONSISTENT = "DECK.IMAGE_SCALE_INCONSISTENT"
DECK_CHROME_INCONSISTENT = "DECK.CHROME_INCONSISTENT"
DECK_PALETTE_DRIFT = "DECK.PALETTE_DRIFT"
DECK_COMPOSITION_FAMILY_DEVIATION = "DECK.COMPOSITION_FAMILY_DEVIATION"
DECK_COMPOSITION_INTENSITY_DRIFT = "DECK.COMPOSITION_INTENSITY_DRIFT"


class DeckQAFinding(DomainModel):
    """One cross-page consistency observation."""

    rule_code: str = Field(min_length=1)
    severity: LayoutIssueSeverity = LayoutIssueSeverity.WARNING
    message: str = Field(min_length=1)
    suggestion: str | None = None
    slide_ids: list[str] = Field(default_factory=list)
    evidence: dict[str, object] = Field(default_factory=dict)


class DeckQADimensions(DomainModel):
    """Deck consistency scores in [0, 1]. None = skipped."""

    layout_variety: float | None = Field(default=None, ge=0.0, le=1.0)
    footer_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    typography_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    section_transition: float | None = Field(default=None, ge=0.0, le=1.0)
    image_scale_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    chrome_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    palette_consistency: float | None = Field(default=None, ge=0.0, le=1.0)


class DeckQAReport(DomainModel):
    """Cross-page Visual QA for an entire visual composition deck."""

    score_kind: str = Field(default="deck_consistency")
    method: str = Field(default="deck_heuristic_v0", min_length=1)
    slide_count: int = Field(default=0, ge=0)
    dimensions: DeckQADimensions = Field(default_factory=DeckQADimensions)
    findings: list[DeckQAFinding] = Field(default_factory=list)
    total_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def finding_codes(self) -> list[str]:
        return sorted({item.rule_code for item in self.findings})

    @computed_field  # type: ignore[prop-decorator]
    @property
    def blocker_count(self) -> int:
        """Findings that map to gate BLOCKER (Layout CRITICAL → IssueSeverity.BLOCKER)."""
        return sum(1 for item in self.findings if layout_is_gate_blocker(item.severity))
