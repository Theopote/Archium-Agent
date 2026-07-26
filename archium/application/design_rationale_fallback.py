"""Synthesize DesignRationale when LLM omits the reasoning chain."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_rationale import DesignRationale


def ensure_direction_design_rationale(
    direction: ConceptDirection,
    *,
    known_facts: dict[str, str] | None = None,
    idea_text: str = "",
) -> ConceptDirection:
    """Ensure a rationale exists; never overwrite an LLM-authored reasoning chain.

    - If chain slots are present → leave rationale untouched.
    - If claim skeleton only (statement/reasons/…) → backfill empty chain slots.
    - If missing/empty → synthesize a full minimal rationale.
    """
    existing = direction.design_rationale
    if existing is not None and existing.has_reasoning_chain():
        return direction

    synth = synthesize_design_rationale_from_direction(
        direction,
        known_facts=known_facts,
        idea_text=idea_text,
    )
    if synth is None:
        return direction

    if existing is None or existing.is_empty():
        return direction.model_copy(update={"design_rationale": synth})

    # Claim-only LLM output: fill empty chain slots only; never replace claim fields.
    merged = existing.model_copy(
        update={
            "observation": existing.observation.strip() or synth.observation,
            "interpretation": existing.interpretation.strip() or synth.interpretation,
            "problem": existing.problem.strip() or synth.problem,
            "hypothesis": existing.hypothesis.strip() or synth.hypothesis,
            "strategy": existing.strategy.strip() or synth.strategy,
            "risks": list(existing.risks) or list(synth.risks),
        }
    )
    return direction.model_copy(update={"design_rationale": merged})


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

    observation = (idea_text or "").strip()[:300]
    problem = (direction.summary or "").strip()[:300]
    strategy = (
        direction.spatial_strategy or direction.spatial_idea or ""
    ).strip()[:300]
    interpretation = ""
    if observation and problem and observation != problem:
        interpretation = f"条件指向：{problem[:120]}"

    rationale = DesignRationale(
        statement=statement,
        reasons=reasons[:5],
        evidence=evidence[:6],
        confidence=confidence,
        observation=observation,
        interpretation=interpretation,
        problem=problem,
        hypothesis=statement[:300],
        strategy=strategy,
        risks=[item.strip() for item in direction.risks if item and item.strip()][:4],
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
