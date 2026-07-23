"""DTOs for natural-language visual edit parsing (domain-owned)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from archium.domain.visual.edit_intent import VisualEditIntent


class ModifierType(StrEnum):
    """Types of instruction modifiers."""

    RELATIVE = "relative"  # 稍微、再大一点
    CONSTRAINT = "constraint"  # 但不要、保持...不动
    MULTI_STEP = "multi_step"  # 换位置、重新排列
    SEMANTIC = "semantic"  # 突出、收紧、更专业


@dataclass(frozen=True)
class Modifier:
    """A modifier that affects how an intent is executed."""

    type: ModifierType
    target: str | None = None  # 受影响的元素
    value: Any = None  # 修改值（如程度、约束条件）
    description: str = ""  # 人类可读的描述


@dataclass(frozen=True)
class ParsedIntent:
    """Structured representation of parsed natural language intent."""

    intent: VisualEditIntent
    params: dict[str, Any]
    modifiers: list[Modifier]
    confidence: float  # 0.0-1.0
    complexity: ModifierType | None = None
