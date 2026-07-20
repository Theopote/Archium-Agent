"""LLM-based parser for complex natural language visual edit intents."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.nlp_parser import Modifier, ModifierType, ParsedIntent
from archium.infrastructure.llm.base import LLMRequest

if TYPE_CHECKING:
    from archium.infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class _IntentParseDraft(BaseModel):
    """Structured output schema for LLM intent parsing."""

    intent: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    modifiers: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0


class LLMIntentParser:
    """Parse complex natural language instructions using LLM."""

    SYSTEM_PROMPT = """你是一个演示文稿视觉编辑指令解析器。将用户的自然语言指令解析为结构化的编辑操作。

支持的基础操作：
1. enlarge_hero - 放大主图/主视觉
2. reduce_text - 减少文字内容
3. increase_whitespace - 增加留白
4. change_layout - 切换版式
5. set_hero_asset - 设置主图素材
6. remove_asset - 移除素材
7. lock_element - 锁定元素
8. unlock_element - 解锁元素
9. update_element_text - 更新元素文字
10. set_element_asset - 设置元素素材

支持的修饰符类型：
- relative: 相对调整（稍微、再大一点、略微）
- constraint: 条件约束（但不要、保持...不动、只改...）
- multi_step: 多步骤操作（换位置、重新排列、互换）
- semantic: 语义理解（突出、收紧、更专业、清晰）

版式类型：
- hero: 主视觉版式
- drawing_focus: 图纸版式
- evidence_board: 证据版式
- comparative_matrix: 比较版式
- process_narrative: 流程版式
- analytical_diagram: 分析图版式
- metric_dashboard: 指标版式
- strategy_cards: 策略版式
- textual_argument: 文字版式
- hybrid_canvas: 混合版式

返回 JSON 格式：
{
  "intent": "操作类型",
  "params": {
    "layout_family": "版式类型（如果是 change_layout）",
    "element_id": "元素ID（如适用）",
    "adjustment_strength": 0.0-1.0,
    "constraints": [{"type": "约束类型", "target": "目标元素"}],
    "multi_step_operations": [{"operation": "操作", "targets": ["元素列表"]}],
    "semantic_operations": ["操作列表"]
  },
  "modifiers": [
    {
      "type": "modifier_type",
      "target": "目标（可选）",
      "value": "值",
      "description": "描述"
    }
  ],
  "confidence": 0.0-1.0
}

如果无法理解指令，返回 {"intent": null, "confidence": 0.0}"""

    USER_PROMPT_TEMPLATE = """请解析以下视觉编辑指令：

"{instruction}"

注意：
1. 识别主要意图和所有修饰条件
2. 提取程度副词（如"稍微"、"再"、"更"）并转换为 0.0-1.0 的强度值
3. 识别约束条件（如"但不要改标题"、"保持图片不动"）
4. 对于多步骤操作，分解为具体的目标元素和操作序列
5. 对于语义指令（如"突出"、"收紧"），转换为具体的视觉操作

返回 JSON 格式的解析结果。"""

    def __init__(self, llm_provider: LLMProvider) -> None:
        """
        Initialize LLM parser.

        Args:
            llm_provider: LLM provider instance (compatible with archium.infrastructure.llm)
        """
        self._llm = llm_provider

    def parse(self, text: str) -> ParsedIntent | None:
        """
        Parse natural language text using LLM.

        Args:
            text: Natural language instruction

        Returns:
            ParsedIntent if successfully parsed, None if LLM failed or couldn't understand
        """
        request = LLMRequest(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=self.USER_PROMPT_TEMPLATE.format(instruction=text),
            temperature=0.1,  # 低温度以获得更确定的输出
            max_tokens=800,
            json_mode=True,
        )
        try:
            draft = self._llm.generate_structured(request, _IntentParseDraft)
        except Exception as exc:
            # 记录错误但不抛出，让调用方回退到规则解析
            logger.warning("LLM intent parsing failed: %s", exc)
            return None

        result = self._parse_draft(draft)
        if result is None or result.confidence < 0.5:
            return None

        return result

    def _parse_draft(self, draft: _IntentParseDraft) -> ParsedIntent | None:
        """Convert the validated LLM draft into a ParsedIntent."""
        if not draft.intent:
            return None

        try:
            intent = VisualEditIntent(draft.intent)
        except ValueError:
            return None

        # 解析参数
        params = self._parse_params(draft.params)

        # 解析修饰符
        modifiers = self._parse_modifiers(draft.modifiers)

        # 推断复杂度类型
        complexity = self._infer_complexity(modifiers)

        return ParsedIntent(
            intent=intent,
            params=params,
            modifiers=modifiers,
            confidence=draft.confidence,
            complexity=complexity,
        )

    def _parse_params(self, params_data: dict[str, Any]) -> dict[str, Any]:
        """Parse and validate parameters."""
        params: dict[str, Any] = {}

        # 版式类型
        if "layout_family" in params_data:
            with suppress(ValueError):
                params["layout_family"] = LayoutFamily(params_data["layout_family"])

        # 元素 ID
        if "element_id" in params_data:
            params["element_id"] = str(params_data["element_id"])

        # 调整强度
        if "adjustment_strength" in params_data:
            strength = float(params_data["adjustment_strength"])
            params["adjustment_strength"] = max(0.0, min(1.0, strength))

        # 约束条件
        if "constraints" in params_data:
            params["constraints"] = params_data["constraints"]

        # 多步骤操作
        if "multi_step_operations" in params_data:
            params["multi_step_operations"] = params_data["multi_step_operations"]

        # 语义操作
        if "semantic_operations" in params_data:
            params["semantic_operations"] = params_data["semantic_operations"]

        # 复制其他参数
        for key, value in params_data.items():
            if key not in params:
                params[key] = value

        return params

    def _parse_modifiers(self, modifiers_data: list[dict[str, Any]]) -> list[Modifier]:
        """Parse modifiers from LLM response."""
        modifiers: list[Modifier] = []

        for mod_data in modifiers_data:
            try:
                mod_type = ModifierType(mod_data["type"])
                modifiers.append(
                    Modifier(
                        type=mod_type,
                        target=mod_data.get("target"),
                        value=mod_data.get("value"),
                        description=mod_data.get("description", ""),
                    )
                )
            except (KeyError, ValueError):
                continue

        return modifiers

    def _infer_complexity(self, modifiers: list[Modifier]) -> ModifierType | None:
        """Infer the primary complexity type from modifiers."""
        if not modifiers:
            return None

        # 统计每种类型的出现次数
        type_counts: dict[ModifierType, int] = {}
        for modifier in modifiers:
            type_counts[modifier.type] = type_counts.get(modifier.type, 0) + 1

        # 返回最常见的类型
        return max(type_counts, key=lambda modifier_type: type_counts[modifier_type])
