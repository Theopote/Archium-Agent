"""Synthesize DesignRationale when LLM omits it on concept direction generation."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale


def ensure_direction_design_rationale(
    direction: ConceptDirection,
    *,
    known_facts: dict[str, str] | None = None,
    idea_text: str = "",
) -> ConceptDirection:
    """Return direction with a rule-based rationale when the model left it empty."""
    if direction.design_rationale is not None and not direction.design_rationale.is_empty():
        return direction
    rationale = synthesize_design_rationale_from_direction(
        direction,
        known_facts=known_facts,
        idea_text=idea_text,
    )
    if rationale is None:
        return direction
    return direction.model_copy(update={"design_rationale": rationale})


def synthesize_design_rationale_from_direction(
    direction: ConceptDirection,
    *,
    known_facts: dict[str, str] | None = None,
    idea_text: str = "",
) -> DesignRationale | None:
    """Build a minimal rationale from structured direction fields and known facts."""
    statement = _primary_statement(direction)
    if not statement:
        return None

    reasons: list[str] = []
    for label, value in (
        ("空间策略", direction.spatial_strategy),
        ("形式语言", direction.formal_language),
        ("材料策略", direction.material_strategy),
        ("体验焦点", direction.experience_focus),
        ("差异点", direction.differentiator),
    ):
        text = (value or "").strip()
        if text and text not in statement:
            reasons.append(f"{label}：{text}")

    evidence: list[str] = []
    for key, value in (known_facts or {}).items():
        text = (value or "").strip()
        if text:
            evidence.append(f"{key}：{text}")
    snippet = " ".join((idea_text or "").split())
    if snippet:
        evidence.append(f"初始想法：{snippet[:160]}")

    confidence = 0.45
    if evidence:
        confidence = min(0.62, 0.45 + 0.04 * len(evidence))

    rationale = DesignRationale(
        statement=statement,
        reasons=reasons[:5],
        evidence=evidence[:6],
        confidence=confidence,
    )
    return None if rationale.is_empty() else rationale


def _primary_statement(direction: ConceptDirection) -> str:
    for value in (
        direction.spatial_strategy,
        direction.spatial_idea,
        direction.summary,
        direction.title,
    ):
        text = (value or "").strip()
        if text:
            return text
    return ""
