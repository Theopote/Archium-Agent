#!/usr/bin/env python3
"""Demo script for enhanced natural language parsing capabilities."""

import sys
from typing import Any


def colorize(text: str, color: str) -> str:
    """Add ANSI color codes to text."""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "red": "\033[91m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(colorize(text.center(70), "cyan"))
    print("=" * 70 + "\n")


def print_section(title: str) -> None:
    """Print a section title."""
    print(colorize(f"\n▶ {title}", "blue"))
    print("-" * 70)


def print_example(instruction: str, description: str) -> None:
    """Print an example instruction."""
    print(f"\n  输入: {colorize(instruction, 'yellow')}")
    print(f"  说明: {description}")


def simulate_parse(instruction: str) -> dict[str, Any]:
    """Simulate parsing an instruction."""
    result = {
        "intent": None,
        "params": {},
        "modifiers": [],
        "confidence": 0.0,
    }

    instruction_lower = instruction.lower()

    # Detect intent
    if "放大" in instruction or "大" in instruction:
        result["intent"] = "ENLARGE_HERO"
    elif "减少文字" in instruction:
        result["intent"] = "REDUCE_TEXT"
    elif "留白" in instruction:
        result["intent"] = "INCREASE_WHITESPACE"
    elif "版式" in instruction or "切换" in instruction:
        result["intent"] = "CHANGE_LAYOUT"

    # Detect degree modifiers
    degree_map = {"稍微": 0.3, "再": 0.4, "更": 0.5, "很": 0.7, "非常": 0.8}
    for word, strength in degree_map.items():
        if word in instruction:
            result["params"]["adjustment_strength"] = strength
            result["modifiers"].append({
                "type": "relative",
                "value": strength,
                "description": f"程度: {word} ({strength})"
            })
            break

    # Detect constraints
    if "但不要" in instruction or "但别" in instruction:
        result["params"]["constraints"] = [{"type": "negative_constraint"}]
        result["modifiers"].append({
            "type": "constraint",
            "description": "约束: 不要盖住其他元素"
        })

    if "保持" in instruction and ("不动" in instruction or "不变" in instruction):
        if "constraints" not in result["params"]:
            result["params"]["constraints"] = []
        result["params"]["constraints"].append({"type": "preserve"})
        result["modifiers"].append({
            "type": "constraint",
            "description": "约束: 保持元素不变"
        })

    # Detect semantics
    semantic_map = {
        "突出": ["emphasis", ["increase_size", "add_contrast"]],
        "收紧": ["tighten", ["reduce_spacing"]],
        "专业": ["professional", ["simplify", "align"]],
    }
    for word, (semantic_type, ops) in semantic_map.items():
        if word in instruction:
            result["params"]["semantic_operations"] = ops
            result["modifiers"].append({
                "type": "semantic",
                "value": semantic_type,
                "description": f"语义: {semantic_type}"
            })
            break

    # Calculate confidence
    if result["intent"]:
        base_confidence = 0.8 - len(result["modifiers"]) * 0.05
        result["confidence"] = max(0.3, min(1.0, base_confidence))

    return result


def print_parse_result(result: dict[str, Any]) -> None:
    """Print the parsing result."""
    if result["intent"]:
        print(f"\n  {colorize('✓', 'green')} 解析成功")
        print(f"    意图: {colorize(result['intent'], 'magenta')}")
        confidence_str = f"{result['confidence']:.2f}"
        print(f"    置信度: {colorize(confidence_str, 'cyan')}")

        if result["params"]:
            print(f"    参数:")
            for key, value in result["params"].items():
                print(f"      • {key}: {value}")

        if result["modifiers"]:
            print(f"    修饰符:")
            for mod in result["modifiers"]:
                print(f"      • {mod['description']}")
    else:
        print(f"\n  {colorize('✗', 'red')} 无法解析")


def demo_all() -> None:
    """Run all demos."""
    print_header("Archium Agent - 增强自然语言解析演示")
    
    print_section("1. 基础指令")
    for instruction, desc in [
        ("放大主图", "简单的放大操作"),
        ("减少文字", "减少文字内容"),
    ]:
        print_example(instruction, desc)
        print_parse_result(simulate_parse(instruction))
    
    print_section("2. 相对调整")
    for instruction, desc in [
        ("稍微放大主图", "轻微放大，强度 ~0.3"),
        ("再大一点主图", "适度放大，强度 ~0.4"),
    ]:
        print_example(instruction, desc)
        print_parse_result(simulate_parse(instruction))
    
    print_section("3. 条件约束")
    for instruction, desc in [
        ("放大主图但不要盖住标题", "放大的同时避免覆盖标题"),
        ("减少文字保持图片不动", "只调整文字，不动图片"),
    ]:
        print_example(instruction, desc)
        print_parse_result(simulate_parse(instruction))
    
    print_header("演示完成")


if __name__ == "__main__":
    demo_all()
