"""Rule-based natural language parser for visual edit intents."""

from __future__ import annotations

import re
from typing import Any

from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.parsed_intent import Modifier, ModifierType, ParsedIntent


class EnhancedNLPParser:
    """Enhanced rule-based parser with support for complex instructions."""

    # 程度副词映射
    DEGREE_MODIFIERS = {
        "稍微": 0.3,
        "稍稍": 0.3,
        "一点": 0.3,
        "一点点": 0.2,
        "略微": 0.25,
        "再": 0.4,
        "更": 0.5,
        "非常": 0.8,
        "很": 0.7,
        "极": 0.9,
        "significantly": 0.7,
        "slightly": 0.3,
        "a bit": 0.3,
        "much": 0.7,
        "very": 0.8,
    }

    # 约束关键词
    CONSTRAINT_PATTERNS = [
        (r"但(不要|别|不)(.*?)", "negative_constraint"),
        (r"保持(.*?)(不动|不变)", "preserve"),
        (r"不要(改|动|碰)(.*?)", "dont_touch"),
        (r"只(.*?)", "only"),
        (r"except", "exclude"),
        (r"but (not|don't)", "negative_constraint"),
        (r"keep (.*?) (unchanged|same)", "preserve"),
    ]

    # 语义动词映射
    SEMANTIC_VERBS = {
        "突出": ("emphasis", ["increase_size", "add_contrast", "reposition"]),
        "强调": ("emphasis", ["increase_size", "add_contrast"]),
        "收紧": ("tighten", ["reduce_spacing", "increase_density"]),
        "放松": ("relax", ["increase_spacing", "reduce_density"]),
        "专业": ("professional", ["simplify", "align", "consistent_spacing"]),
        "清晰": ("clarity", ["increase_whitespace", "larger_text", "reduce_elements"]),
        "紧凑": ("compact", ["reduce_spacing", "smaller_elements"]),
        "平衡": ("balance", ["redistribute_elements", "center_align"]),
        "highlight": ("emphasis", ["increase_size", "add_contrast"]),
        "tighten": ("tighten", ["reduce_spacing"]),
        "clean": ("professional", ["simplify", "align"]),
    }

    # 位置操作关键词
    POSITION_PATTERNS = [
        (r"(.*?)换到(.*?)位置", "swap"),
        (r"把(.*?)移到(.*?)", "move_to"),
        (r"(.*?)和(.*?)互换", "exchange"),
        (r"重新排列", "rearrange"),
        (r"调整顺序", "reorder"),
        (r"move (.*?) to", "move_to"),
        (r"swap (.*?) (with|and)", "swap"),
    ]

    def parse(self, text: str) -> ParsedIntent | None:
        """
        Parse natural language text into structured intent.

        Returns ParsedIntent if successfully parsed, None if too complex for rules.
        """
        normalized = self._normalize(text)

        complexity = self._detect_complexity(normalized)

        intent, base_params = self._parse_base_intent(normalized)
        if intent is None:
            return None

        modifiers = self._extract_modifiers(normalized, intent)

        params = self._merge_params(base_params, modifiers)

        confidence = self._calculate_confidence(intent, modifiers, complexity)

        if confidence < 0.6 or (complexity and len(modifiers) > 2):
            return None

        return ParsedIntent(
            intent=intent,
            params=params,
            modifiers=modifiers,
            confidence=confidence,
            complexity=complexity,
        )

    def _normalize(self, text: str) -> str:
        """Normalize input text."""
        text = " ".join(text.strip().split())
        text = text.replace("，", " ").replace("。", " ").replace("、", " ")
        return text.lower()

    def _detect_complexity(self, text: str) -> ModifierType | None:
        """Detect the primary complexity type in the instruction."""
        if any(degree in text for degree in self.DEGREE_MODIFIERS):
            return ModifierType.RELATIVE

        for pattern, _ in self.CONSTRAINT_PATTERNS:
            if re.search(pattern, text):
                return ModifierType.CONSTRAINT

        for pattern, _ in self.POSITION_PATTERNS:
            if re.search(pattern, text):
                return ModifierType.MULTI_STEP

        if any(verb in text for verb in self.SEMANTIC_VERBS):
            return ModifierType.SEMANTIC

        return None

    def _parse_base_intent(self, text: str) -> tuple[VisualEditIntent | None, dict[str, Any]]:
        """Parse the base intent (similar to original parse_natural_language)."""
        from archium.domain.visual.edit_intent import parse_natural_language

        return parse_natural_language(text)

    def _extract_modifiers(self, text: str, intent: VisualEditIntent) -> list[Modifier]:
        """Extract all modifiers from the text."""
        modifiers: list[Modifier] = []

        for degree_word, strength in self.DEGREE_MODIFIERS.items():
            if degree_word in text:
                modifiers.append(
                    Modifier(
                        type=ModifierType.RELATIVE,
                        value=strength,
                        description=f"程度: {degree_word} ({strength})",
                    )
                )

        for pattern, constraint_type in self.CONSTRAINT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                target = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                modifiers.append(
                    Modifier(
                        type=ModifierType.CONSTRAINT,
                        target=target,
                        value=constraint_type,
                        description=f"约束: {constraint_type} ({target or ''})",
                    )
                )

        for pattern, operation in self.POSITION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                targets = (
                    [match.group(i) for i in range(1, match.lastindex + 1)] if match.lastindex else []
                )
                modifiers.append(
                    Modifier(
                        type=ModifierType.MULTI_STEP,
                        value={"operation": operation, "targets": targets},
                        description=f"位置操作: {operation}",
                    )
                )

        for verb, (semantic_type, operations) in self.SEMANTIC_VERBS.items():
            if verb in text:
                modifiers.append(
                    Modifier(
                        type=ModifierType.SEMANTIC,
                        value={"type": semantic_type, "operations": operations},
                        description=f"语义: {semantic_type}",
                    )
                )

        return modifiers

    def _merge_params(self, base_params: dict[str, Any], modifiers: list[Modifier]) -> dict[str, Any]:
        """Merge base parameters with modifier-derived parameters."""
        params = base_params.copy()

        relative_mods = [m for m in modifiers if m.type == ModifierType.RELATIVE]
        if relative_mods:
            max_strength = max(m.value for m in relative_mods if isinstance(m.value, (int, float)))
            params["adjustment_strength"] = max_strength

        constraints = [m for m in modifiers if m.type == ModifierType.CONSTRAINT]
        if constraints:
            params["constraints"] = [{"type": m.value, "target": m.target} for m in constraints]

        multi_steps = [m for m in modifiers if m.type == ModifierType.MULTI_STEP]
        if multi_steps:
            params["multi_step_operations"] = [m.value for m in multi_steps]

        semantic_mods = [m for m in modifiers if m.type == ModifierType.SEMANTIC]
        if semantic_mods:
            all_operations = []
            for mod in semantic_mods:
                if isinstance(mod.value, dict) and "operations" in mod.value:
                    all_operations.extend(mod.value["operations"])
            params["semantic_operations"] = all_operations

        return params

    def _calculate_confidence(
        self,
        intent: VisualEditIntent,
        modifiers: list[Modifier],
        complexity: ModifierType | None,
    ) -> float:
        """Calculate confidence score for the parse."""
        confidence = 0.8
        confidence -= len(modifiers) * 0.05

        complexity_penalty = {
            ModifierType.RELATIVE: 0.0,
            ModifierType.CONSTRAINT: 0.1,
            ModifierType.MULTI_STEP: 0.2,
            ModifierType.SEMANTIC: 0.15,
        }
        if complexity:
            confidence -= complexity_penalty.get(complexity, 0.0)

        return max(0.0, min(1.0, confidence))
