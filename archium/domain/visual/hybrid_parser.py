"""Hybrid parser that routes between rule-based and LLM-based parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from archium.domain.visual.nlp_parser import EnhancedNLPParser, ParsedIntent

if TYPE_CHECKING:
    from archium.domain.visual.llm_parser import LLMIntentParser


class HybridIntentParser:
    """
    Hybrid parser that intelligently routes between rule-based and LLM parsing.

    Strategy:
    1. Try enhanced rule-based parser first (fast, deterministic)
    2. If rules return low confidence or None, fall back to LLM
    3. If LLM is disabled or fails, return best-effort rule result
    """

    # 置信度阈值：低于此值时尝试 LLM
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, llm_parser: LLMIntentParser | None = None) -> None:
        """
        Initialize hybrid parser.

        Args:
            llm_parser: Optional LLM parser for complex instructions
        """
        self._rule_parser = EnhancedNLPParser()
        self._llm_parser = llm_parser

    def parse(self, text: str) -> ParsedIntent | None:
        """
        Parse natural language instruction using hybrid approach.

        Args:
            text: Natural language instruction

        Returns:
            ParsedIntent if successfully parsed, None if cannot understand
        """
        # 第一步：尝试规则解析
        rule_result = self._rule_parser.parse(text)

        # 如果规则解析成功且置信度高，直接返回
        if rule_result and rule_result.confidence >= self.CONFIDENCE_THRESHOLD:
            return rule_result

        # 第二步：如果规则失败或置信度低，尝试 LLM
        if self._llm_parser is not None:
            llm_result = self._llm_parser.parse(text)

            # LLM 成功解析
            if llm_result and llm_result.confidence >= 0.5:
                # 如果 LLM 置信度明显高于规则，使用 LLM 结果
                if rule_result is None or llm_result.confidence > rule_result.confidence + 0.1:
                    return llm_result

                # 否则，返回置信度更高的结果
                return llm_result if llm_result.confidence >= rule_result.confidence else rule_result

        # 第三步：回退到规则结果（即使置信度低）
        return rule_result

    def should_use_llm(self, text: str) -> bool:
        """
        Determine if LLM should be used for this instruction.

        This is a fast heuristic check before actually parsing.

        Args:
            text: Natural language instruction

        Returns:
            True if instruction likely needs LLM, False if rules should suffice
        """
        # 如果没有 LLM，总是返回 False
        if self._llm_parser is None:
            return False

        normalized = text.lower().strip()

        # 启发式：检测复杂性指标
        complexity_indicators = [
            # 多个条件
            len([word for word in ["但", "不要", "只", "保持", "but", "except", "keep", "don't"] if word in normalized]) > 1,
            # 长指令（超过20字符中文或40字符英文）
            len(text) > 40,
            # 多个逗号或句号
            text.count("，") + text.count("。") + text.count(",") + text.count(".") > 2,
            # 包含"和"或"并且"表示多个操作
            "和" in normalized or "并且" in normalized or " and " in normalized,
            # 包含比较或序列
            any(word in normalized for word in ["比", "更", "先", "然后", "接着", "first", "then", "more", "less"]),
        ]

        # 如果有多个复杂性指标，建议使用 LLM
        return sum(complexity_indicators) >= 2


def create_hybrid_parser(
    llm_provider=None,
    *,
    use_llm: bool = True,
) -> HybridIntentParser:
    """
    Factory function to create hybrid parser.

    Args:
        llm_provider: LLM provider instance (optional)
        use_llm: Whether to enable LLM parsing

    Returns:
        Configured HybridIntentParser
    """
    llm_parser = None
    if use_llm and llm_provider is not None:
        from archium.domain.visual.llm_parser import LLMIntentParser
        llm_parser = LLMIntentParser(llm_provider)

    return HybridIntentParser(llm_parser=llm_parser)
