"""Direction ↔ DesignIntent sync contract (DOM-024).

ConceptDirection and DesignIntent both nest Rationale / Spatial / Rules.
After select/commit, Intent is a projection of Direction — this module detects
drift without forcing a single nested store.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.domain.concept_direction import ConceptDirection
from archium.domain.intent.design_intent import DesignIntent


@dataclass(frozen=True)
class DirectionIntentDiff:
    """Explicit drift between a direction and a projected intent."""

    fields: tuple[str, ...] = ()

    @property
    def aligned(self) -> bool:
        return not self.fields

    def display_line(self) -> str:
        if self.aligned:
            return "方向与意图一致"
        return "漂移字段：" + "、".join(self.fields)


def _norm(text: str | None) -> str:
    return (text or "").strip()


def _rationale_key(value: object | None) -> str:
    if value is None:
        return ""
    statement = _norm(getattr(value, "statement", None))
    strategy = _norm(getattr(value, "strategy", None))
    return f"{statement}|{strategy}"


def _spatial_key(value: object | None) -> str:
    if value is None:
        return ""
    parts = [
        _norm(getattr(value, "spatial_relationships", None)),
        _norm(getattr(value, "movement_experience", None)),
        _norm(getattr(value, "public_private_structure", None)),
        _norm(getattr(value, "light_strategy", None)),
        _norm(getattr(value, "landscape_relation", None)),
    ]
    return "|".join(parts)


def _rules_key(rules: list[object] | None) -> str:
    lines: list[str] = []
    for rule in rules or []:
        line = ""
        if hasattr(rule, "to_prompt_line"):
            try:
                line = _norm(rule.to_prompt_line())
            except Exception:
                line = _norm(str(rule))
        else:
            line = _norm(str(rule))
        if line:
            lines.append(line)
    return "\n".join(lines)


def diff_direction_intent(
    direction: ConceptDirection,
    intent: DesignIntent,
) -> DirectionIntentDiff:
    """Compare shared nested fields; Intent-only overlays (social_background…) ignored."""
    drifts: list[str] = []
    # Theme: prefer explicit direction.theme; title fallback only when Intent is linked.
    direction_theme = _norm(direction.theme)
    if direction_theme:
        if direction_theme != _norm(intent.theme):
            drifts.append("theme")
    elif intent.source_direction_id == direction.id:
        expected_theme = _norm(direction.title)
        if expected_theme and expected_theme != _norm(intent.theme):
            drifts.append("theme")
    expected_problem = _norm(direction.summary)
    if expected_problem and expected_problem != _norm(intent.problem_statement):
        drifts.append("problem_statement")
    expected_experience = _norm(direction.experience_focus)
    if expected_experience and expected_experience != _norm(intent.desired_experience):
        drifts.append("desired_experience")
    if direction.design_rationale is not None:
        if _rationale_key(direction.design_rationale) != _rationale_key(
            intent.design_rationale
        ):
            drifts.append("design_rationale")
    if direction.spatial_intent is not None:
        if _spatial_key(direction.spatial_intent) != _spatial_key(intent.spatial_intent):
            drifts.append("spatial_intent")
    if direction.design_rules:
        if _rules_key(list(direction.design_rules)) != _rules_key(
            list(intent.design_rules)
        ):
            drifts.append("design_rules")
    if intent.source_direction_id is not None and intent.source_direction_id != direction.id:
        drifts.append("source_direction_id")
    return DirectionIntentDiff(fields=tuple(drifts))


def is_direction_intent_aligned(
    direction: ConceptDirection,
    intent: DesignIntent,
) -> bool:
    return diff_direction_intent(direction, intent).aligned


def source_direction_matches(
    intent: DesignIntent,
    direction_id: UUID,
) -> bool:
    return intent.source_direction_id == direction_id
