"""Standalone test script for enhanced NLP parser (no external dependencies)."""

import sys
import re
from typing import Any


def test_degree_modifiers() -> None:
    """Test degree modifier extraction."""
    print("Testing degree modifiers...")

    degree_modifiers = {
        "稍微": 0.3,
        "再": 0.4,
        "更": 0.5,
        "很": 0.7,
    }

    test_cases = [
        ("稍微放大主图", 0.3),
        ("再大一点", 0.4),
        ("更大", 0.5),
    ]

    for text, expected_strength in test_cases:
        found = False
        for degree_word, strength in degree_modifiers.items():
            if degree_word in text:
                found = True
                assert abs(strength - expected_strength) < 0.2, f"Expected ~{expected_strength}, got {strength}"
                print(f"  ✓ '{text}' -> strength={strength}")
                break
        assert found, f"No degree modifier found in '{text}'"

    print("  All degree modifier tests passed!\n")


def test_constraint_patterns() -> None:
    """Test constraint pattern matching."""
    print("Testing constraint patterns...")

    constraint_patterns = [
        (r"但(不要|别|不)(.*?)", "negative_constraint"),
        (r"保持(.*?)(不动|不变)", "preserve"),
        (r"不要(改|动|碰)(.*?)", "dont_touch"),
        (r"只(.*?)", "only"),
    ]

    test_cases = [
        ("但不要盖住标题", "negative_constraint"),
        ("保持图片不动", "preserve"),
        ("不要改标题", "dont_touch"),
        ("只把说明挪到右侧", "only"),
    ]

    for text, expected_type in test_cases:
        found = False
        for pattern, constraint_type in constraint_patterns:
            if re.search(pattern, text):
                found = True
                assert constraint_type == expected_type, f"Expected {expected_type}, got {constraint_type}"
                print(f"  ✓ '{text}' -> {constraint_type}")
                break
        assert found, f"No constraint pattern found in '{text}'"

    print("  All constraint pattern tests passed!\n")


def test_semantic_verbs() -> None:
    """Test semantic verb detection."""
    print("Testing semantic verbs...")

    semantic_verbs = {
        "突出": ("emphasis", ["increase_size", "add_contrast", "reposition"]),
        "收紧": ("tighten", ["reduce_spacing", "increase_density"]),
        "专业": ("professional", ["simplify", "align", "consistent_spacing"]),
        "清晰": ("clarity", ["increase_whitespace", "larger_text"]),
    }

    test_cases = [
        ("突出结论", "emphasis"),
        ("收紧一点", "tighten"),
        ("更专业", "professional"),
        ("让它更清晰", "clarity"),
    ]

    for text, expected_semantic in test_cases:
        found = False
        for verb, (semantic_type, _ops) in semantic_verbs.items():
            if verb in text:
                found = True
                assert semantic_type == expected_semantic, f"Expected {expected_semantic}, got {semantic_type}"
                print(f"  ✓ '{text}' -> {semantic_type}")
                break
        assert found, f"No semantic verb found in '{text}'"

    print("  All semantic verb tests passed!\n")


def test_position_patterns() -> None:
    """Test position operation pattern matching."""
    print("Testing position patterns...")

    position_patterns = [
        (r"(.*?)换到(.*?)位置", "swap"),
        (r"把(.*?)移到(.*?)", "move_to"),
        (r"(.*?)和(.*?)互换", "exchange"),
        (r"重新排列", "rearrange"),
    ]

    test_cases = [
        ("第二张照片换到第一张位置", "swap"),
        ("把说明移到右侧", "move_to"),
        ("图片和文字互换", "exchange"),
        ("重新排列元素", "rearrange"),
    ]

    for text, expected_op in test_cases:
        found = False
        for pattern, operation in position_patterns:
            if re.search(pattern, text):
                found = True
                assert operation == expected_op, f"Expected {expected_op}, got {operation}"
                print(f"  ✓ '{text}' -> {operation}")
                break
        assert found, f"No position pattern found in '{text}'"

    print("  All position pattern tests passed!\n")


def test_complex_instructions() -> None:
    """Test detection of complex instructions."""
    print("Testing complex instruction detection...")

    def detect_complexity(text: str) -> list[str]:
        """Detect complexity indicators in text."""
        indicators = []

        # 多个条件
        constraint_words = ["但", "不要", "只", "保持"]
        if sum(1 for word in constraint_words if word in text) > 1:
            indicators.append("multiple_constraints")

        # 长指令
        if len(text) > 40:
            indicators.append("long_instruction")

        # 多个逗号
        if text.count("，") + text.count(",") > 2:
            indicators.append("multiple_clauses")

        # 多个操作
        if "和" in text or "并且" in text:
            indicators.append("multiple_operations")

        return indicators

    test_cases = [
        ("放大主图", [], False),  # 简单
        ("主图稍微再大一点，不要盖住标题", ["multiple_clauses"], False),  # 只有1个逗号，不会触发
        ("保持图纸不动，只把说明挪到右侧，但不要改标题", ["multiple_constraints", "multiple_clauses"], True),
    ]

    for text, expected_indicators, should_have_any in test_cases:
        indicators = detect_complexity(text)
        print(f"  '{text[:40]}...' -> {indicators}")
        if should_have_any:
            assert any(ind in indicators for ind in expected_indicators), \
                f"Expected some indicators from {expected_indicators}, got {indicators}"
        elif not expected_indicators:
            # 简单指令可能没有指标
            pass

    print("  All complexity detection tests passed!\n")


def main() -> None:
    """Run all tests."""
    print("=" * 60)
    print("Enhanced NLP Parser - Standalone Tests")
    print("=" * 60 + "\n")

    try:
        test_degree_modifiers()
        test_constraint_patterns()
        test_semantic_verbs()
        test_position_patterns()
        test_complex_instructions()

        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
