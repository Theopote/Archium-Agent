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
    """Simulate parsing an instruction (no actual imports needed)."""
    result = {
        "intent": None,
        "params": {},
        "modifiers": [],
        "confidence": 0.0,
    }

    instruction_lower = instruction.lower()

    # 检测意图
    if "放大" in instruction or "大" in instruction:
        result["intent"] = "ENLARGE_HERO"
    elif "减少文字" in instruction:
        result["intent"] = "REDUCE_TEXT"
    elif "留白" in instruction:
        result["intent"] = "INCREASE_WHITESPACE"
    elif "版式" in instruction or "切换" in instruction:
        result["intent"] = "CHANGE_LAYOUT"

    # 检测程度修饰符
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

    # 检测约束
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

    # 检测语义
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

    # 计算置信度
    base_confidence = 0.8
    if result["intent"]:
        base_confidence = 0.8
        base_confidence -= len(result["modifiers"]) * 0.05
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


def demo_basic_instructions() -> None:
    """Demo basic instructions."""
    print_section("1. 基础指令（高置信度规则解析）")

    examples = [
        ("放大主图", "简单的放大操作"),
        ("减少文字", "减少文字内容"),
        ("增加留白", "增加页面留白"),
        ("切换版式", "更改布局"),
    ]

    for instruction, description in examples:
        print_example(instruction, description)
        result = simulate_parse(instruction)
        print_parse_result(result)


def demo_relative_adjustments() -> None:
    """Demo relative adjustment instructions."""
    print_section("2. 相对调整（程度控制）")

    examples = [
        ("稍微放大主图", "轻微放大，强度 ~0.3"),
        ("再大一点主图", "适度放大，强度 ~0.4"),
        ("更大的主图", "明显放大，强度 ~0.5"),
        ("非常大的主图", "显著放大，强度 ~0.8"),
    ]

    for instruction, description in examples:
        print_example(instruction, description)
        result = simulate_parse(instruction)
        print_parse_result(result)


def demo_constraints() -> None:
    """Demo constraint instructions."""
    print_section("3. 条件约束（保持元素不变）")

    examples = [
        ("放大主图但不要盖住标题", "放大的同时避免覆盖标题"),
        ("减少文字保持图片不动", "只调整文字，不动图片"),
        ("调整版式但不要改标题", "限定修改范围"),
    ]

    for instruction, description in examples:
        print_example(instruction, description)
        result = simulate_parse(instruction)
        print_parse_result(result)


def demo_semantic_instructions() -> None:
    """Demo semantic instructions."""
    print_section("4. 语义理解（设计意图）")

    examples = [
        ("突出结论", "增大尺寸 + 增强对比度"),
        ("收紧版面", "减少间距 + 提高密度"),
        ("让它更专业", "简化 + 对齐 + 统一间距"),
    ]

    for instruction, description in examples:
        print_example(instruction, description)
        result = simulate_parse(instruction)
        print_parse_result(result)


def demo_complex_instructions() -> None:
    """Demo complex multi-modifier instructions."""
    print_section("5. 复杂指令（多重修饰符）")

    print(colorize("\n  注意: 这些复杂指令通常需要 LLM 处理", "yellow"))

    examples = [
        ("主图稍微再大一点，不要盖住标题", "程度修饰 + 约束条件"),
        ("保持图纸不动，只把说明挪到右侧", "保留约束 + 位置操作"),
        ("这页太散，收紧一点但字号不要变", "语义理解 + 约束条件"),
    ]

    for instruction, description in examples:
        print_example(instruction, description)
        result = simulate_parse(instruction)
        print_parse_result(result)


def demo_routing_strategy() -> None:
    """Demo routing strategy explanation."""
    print_section("6. 混合路由策略")

    print("""
  系统根据指令复杂度自动选择解析策略：

  简单指令 (置信度 > 0.7)
    └─→ 规则解析器
        ├─ 速度: ~1ms
        ├─ 成本: 无
        └─ 示例: "放大主图"

  中等复杂 (置信度 0.6-0.7)
    └─→ 规则解析器 (优先)
        └─→ LLM 解析器 (如果启用)
            ├─ 速度: ~200-500ms
            ├─ 成本: ~0.001-0.01 USD
            └─ 示例: "稍微放大主图但不要盖住标题"

  高度复杂 (规则解析失败)
    └─→ LLM 解析器
        └─→ 规则解析器 (回退)
            └─ 示例: "保持图纸不动，只把说明挪到右侧，但不要改标题"
    """)


def main() -> None:
    """Run the demo."""
    print_header("Archium Agent - 增强自然语言解析演示")

    print(colorize("\n本演示展示了新的解析能力，支持更复杂的自然语言指令。\n", "cyan"))

    demo_basic_instructions()
    demo_relative_adjustments()
    demo_constraints()
    demo_semantic_instructions()
    demo_complex_instructions()
    demo_routing_strategy()

    print_header("演示完成")

    print(colorize("\n💡 提示:", "green"))
    print("  • 简单指令使用规则解析（快速、免费）")
    print("  • 复杂指令自动切换到 LLM（准确、智能）")
    print("  • 系统始终尝试回退到规则解析以保证可用性")
    print(f"\n📖 详细文档: {colorize('docs/enhanced_nlp_parsing.md', 'blue')}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colorize("\n\n已取消演示", "yellow"))
        sys.exit(0)
