"""Tests for enhanced natural language parsing with complex instructions."""

from __future__ import annotations

import pytest
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.nlp_parser import EnhancedNLPParser, ModifierType


class TestEnhancedNLPParser:
    """Test enhanced rule-based parser."""

    def setup_method(self) -> None:
        self.parser = EnhancedNLPParser()

    def test_parse_simple_intent_without_modifiers(self) -> None:
        """Simple instructions should still work."""
        result = self.parser.parse("放大主图")
        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO
        assert result.confidence > 0.7

    def test_parse_with_degree_modifier(self) -> None:
        """Parse instruction with degree modifier (稍微、再)."""
        result = self.parser.parse("稍微放大主图")
        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO
        assert "adjustment_strength" in result.params
        assert 0.2 <= result.params["adjustment_strength"] <= 0.4  # 稍微 = 0.3
        assert any(m.type == ModifierType.RELATIVE for m in result.modifiers)

    def test_parse_with_stronger_degree_modifier(self) -> None:
        """Parse instruction with stronger degree modifier."""
        result = self.parser.parse("放大主图再大一点")
        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO
        assert result.params["adjustment_strength"] >= 0.3

    def test_parse_with_constraint_negative(self) -> None:
        """Parse instruction with negative constraint (但不要)."""
        result = self.parser.parse("放大主图但不要盖住标题")
        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO
        assert "constraints" in result.params
        constraints = result.params["constraints"]
        assert len(constraints) > 0
        assert any(c["type"] == "negative_constraint" for c in constraints)

    def test_parse_with_preserve_constraint(self) -> None:
        """Parse instruction with preserve constraint (保持...不动)."""
        result = self.parser.parse("减少文字保持图片不动")
        assert result is not None
        assert result.intent == VisualEditIntent.REDUCE_TEXT
        assert "constraints" in result.params
        constraints = result.params["constraints"]
        assert any(c["type"] == "preserve" for c in constraints)

    def test_parse_semantic_instruction(self) -> None:
        """Parse semantic instruction (突出、收紧)."""
        result = self.parser.parse("突出结论")
        # 语义指令可能需要 LLM，规则解析器可能返回 None 或低置信度
        # 但至少应该识别出复杂度
        if result is not None:
            assert result.complexity == ModifierType.SEMANTIC

    def test_parse_change_layout_with_family(self) -> None:
        """Parse layout change with specific family."""
        result = self.parser.parse("切换到图纸版式")
        assert result is not None
        assert result.intent == VisualEditIntent.CHANGE_LAYOUT
        assert result.params.get("layout_family") == LayoutFamily.DRAWING_FOCUS

    def test_parse_complex_instruction_returns_none(self) -> None:
        """Very complex instructions should return None for LLM handling."""
        result = self.parser.parse(
            "主图稍微再大一点，不要盖住标题，把说明挪到右侧，保持图纸不动"
        )
        # 这个太复杂了，应该返回 None 让 LLM 处理
        # 或者置信度很低
        if result is not None:
            assert result.confidence < 0.6

    def test_calculate_confidence_decreases_with_complexity(self) -> None:
        """Confidence should decrease as complexity increases."""
        simple = self.parser.parse("放大主图")
        moderate = self.parser.parse("稍微放大主图")
        complex_inst = self.parser.parse("稍微放大主图但不要盖住标题")

        assert simple is not None
        if moderate is not None:
            assert moderate.confidence <= simple.confidence
        if complex_inst is not None and moderate is not None:
            assert complex_inst.confidence <= moderate.confidence


class TestHybridParser:
    """Test hybrid parser routing logic."""

    def test_simple_instruction_uses_rules(self) -> None:
        """Simple instructions should use rule-based parser."""
        from archium.domain.visual.hybrid_parser import HybridIntentParser

        parser = HybridIntentParser(llm_parser=None)
        result = parser.parse("放大主图")

        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO
        # 应该有高置信度（来自规则）
        assert result.confidence >= 0.7

    def test_should_use_llm_heuristic(self) -> None:
        """Test heuristic for determining if LLM is needed."""
        from unittest.mock import MagicMock

        from archium.domain.visual.hybrid_parser import HybridIntentParser

        parser_without_llm = HybridIntentParser(llm_parser=None)
        assert not parser_without_llm.should_use_llm("放大主图")

        parser = HybridIntentParser(llm_parser=MagicMock())
        assert parser.should_use_llm("主图稍微再大一点，但不要盖住标题，保持图纸不动")

    def test_fallback_when_llm_unavailable(self) -> None:
        """When LLM is unavailable, should fall back to rules."""
        from archium.domain.visual.hybrid_parser import HybridIntentParser

        parser = HybridIntentParser(llm_parser=None)
        result = parser.parse("稍微放大主图")

        assert result is not None
        assert result.intent == VisualEditIntent.ENLARGE_HERO


class TestComplexInstructionExamples:
    """Test specific complex instruction examples from requirements."""

    def setup_method(self) -> None:
        self.parser = EnhancedNLPParser()

    def test_example_1_degree_with_constraint(self) -> None:
        """主图稍微再大一点，不要盖住标题"""
        result = self.parser.parse("主图稍微再大一点，不要盖住标题")
        if result is not None:
            assert result.intent == VisualEditIntent.ENLARGE_HERO
            # 应该有程度修饰符
            assert any(m.type == ModifierType.RELATIVE for m in result.modifiers)
            # 应该有约束
            if "constraints" in result.params:
                assert len(result.params["constraints"]) > 0

    def test_example_2_preserve_with_action(self) -> None:
        """保持图纸不动，只把说明挪到右侧"""
        result = self.parser.parse("保持图纸不动，只把说明挪到右侧")
        # 这个包含多步骤操作，可能需要 LLM
        if result is not None:
            assert "constraints" in result.params or result.complexity == ModifierType.MULTI_STEP

    def test_example_3_semantic_tighten(self) -> None:
        """这页太散，收紧一点但字号不要变"""
        result = self.parser.parse("这页太散，收紧一点但字号不要变")
        # 包含语义理解（收紧）和约束
        if result is not None:
            # 可能识别为增加留白（的反向）或语义操作
            assert result.complexity in {ModifierType.SEMANTIC, ModifierType.CONSTRAINT}

    def test_example_4_swap_positions(self) -> None:
        """第二张照片换到第一张位置"""
        result = self.parser.parse("第二张照片换到第一张位置")
        # 位置交换，多步骤操作
        if result is not None:
            assert result.complexity == ModifierType.MULTI_STEP
            if "multi_step_operations" in result.params:
                ops = result.params["multi_step_operations"]
                assert len(ops) > 0

    def test_example_5_preserve_layout_emphasize(self) -> None:
        """保留这个排版，只把结论更突出"""
        result = self.parser.parse("保留这个排版，只把结论更突出")
        # 包含约束（保留排版）和语义（突出）
        if result is not None:
            has_constraint = any(m.type == ModifierType.CONSTRAINT for m in result.modifiers)
            has_semantic = any(m.type == ModifierType.SEMANTIC for m in result.modifiers)
            assert has_constraint or has_semantic


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
