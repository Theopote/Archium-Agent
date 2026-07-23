"""Hybrid parser that routes between rule-based and LLM-based parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.application.visual.nlp_parser import EnhancedNLPParser
from archium.domain.visual.parsed_intent import ParsedIntent

if TYPE_CHECKING:
    from archium.application.visual.llm_parser import LLMIntentParser
    from archium.infrastructure.llm.base import LLMProvider


class HybridIntentParser:
    """
    Hybrid parser that intelligently routes between rule-based and LLM parsing.

    Strategy:
    1. Try enhanced rule-based parser first (fast, deterministic)
    2. If rules return low confidence or None, fall back to LLM
    3. If LLM is disabled or fails, return best-effort rule result
    """

    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, llm_parser: LLMIntentParser | None = None) -> None:
        self._rule_parser = EnhancedNLPParser()
        self._llm_parser = llm_parser

    def parse(self, text: str) -> ParsedIntent | None:
        """Parse natural language instruction using hybrid approach."""
        rule_result = self._rule_parser.parse(text)

        if rule_result and rule_result.confidence >= self.CONFIDENCE_THRESHOLD:
            return rule_result

        if self._llm_parser is not None:
            llm_result = self._llm_parser.parse(text)

            if llm_result and llm_result.confidence >= 0.5:
                if rule_result is None or llm_result.confidence > rule_result.confidence + 0.1:
                    return llm_result
                return llm_result if llm_result.confidence >= rule_result.confidence else rule_result

        return rule_result

    def should_use_llm(self, text: str) -> bool:
        """Fast heuristic: whether LLM is likely needed for this instruction."""
        if self._llm_parser is None:
            return False

        normalized = text.lower().strip()

        constraint_words = ("但", "不要", "只", "保持", "but", "except", "keep", "don't")
        if sum(1 for word in constraint_words if word in normalized) > 1:
            return True

        complexity_indicators = [
            len(text) > 40,
            text.count("，") + text.count("。") + text.count(",") + text.count(".") > 2,
            "和" in normalized or "并且" in normalized or " and " in normalized,
            any(
                word in normalized
                for word in ["比", "更", "先", "然后", "接着", "first", "then", "more", "less"]
            ),
        ]

        return sum(complexity_indicators) >= 2


def create_hybrid_parser(
    llm_provider: LLMProvider | None = None,
    *,
    use_llm: bool = True,
) -> HybridIntentParser:
    """Factory function to create hybrid parser."""
    llm_parser = None
    if use_llm and llm_provider is not None:
        from archium.application.visual.llm_parser import LLMIntentParser

        llm_parser = LLMIntentParser(llm_provider)

    return HybridIntentParser(llm_parser=llm_parser)
