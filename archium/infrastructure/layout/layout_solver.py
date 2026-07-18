"""Deterministic layout solver — dispatches to family generators."""

from __future__ import annotations

from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout import LayoutPlan
from archium.infrastructure.layout.generators.base import LayoutGenerator, LayoutGeneratorContext
from archium.infrastructure.layout.generators.comparative_matrix import (
    ComparativeMatrixLayoutGenerator,
)
from archium.infrastructure.layout.generators.drawing_focus import DrawingFocusLayoutGenerator
from archium.infrastructure.layout.generators.evidence_board import EvidenceBoardLayoutGenerator
from archium.infrastructure.layout.generators.hero import HeroLayoutGenerator
from archium.infrastructure.layout.generators.strategy_cards import StrategyCardsLayoutGenerator
from archium.infrastructure.layout.generators.textual_argument import (
    TextualArgumentLayoutGenerator,
)


class LayoutSolver:
    """Map LayoutFamily → deterministic generator (no free-form LLM coordinates)."""

    def __init__(self, generators: dict[LayoutFamily, LayoutGenerator] | None = None) -> None:
        self._generators = generators or {
            LayoutFamily.HERO: HeroLayoutGenerator(),
            LayoutFamily.EVIDENCE_BOARD: EvidenceBoardLayoutGenerator(),
            LayoutFamily.DRAWING_FOCUS: DrawingFocusLayoutGenerator(),
            LayoutFamily.COMPARATIVE_MATRIX: ComparativeMatrixLayoutGenerator(),
            LayoutFamily.STRATEGY_CARDS: StrategyCardsLayoutGenerator(),
            LayoutFamily.TEXTUAL_ARGUMENT: TextualArgumentLayoutGenerator(),
        }

    def supported_families(self) -> list[LayoutFamily]:
        return list(self._generators.keys())

    def generate(self, family: LayoutFamily, context: LayoutGeneratorContext) -> LayoutPlan:
        try:
            generator = self._generators[family]
        except KeyError as exc:
            raise KeyError(f"no generator implemented for family: {family}") from exc
        return generator.generate(context)
