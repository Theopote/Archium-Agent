"""Helpers to build and normalize KnowledgeDimensions."""

from __future__ import annotations

from archium.application.context_evidence import ProjectEvidencePack
from archium.domain.intent.knowledge_dimensions import (
    KnowledgeDimensions,
    derive_research_need,
)
from archium.domain.intent.knowledge_state import KnowledgeState


def dimensions_from_draft_values(
    *,
    information_completeness: float | None = None,
    design_intent_clarity: float | None = None,
    evidence_confidence: float | None = None,
    constraint_understanding: float | None = None,
    user_alignment: float | None = None,
    research_need: float | None = None,
    completeness_score: float = 0.0,
    evidence_ratio: float = 0.0,
    assumption_ratio: float = 1.0,
) -> KnowledgeDimensions:
    """Merge LLM dimension fields with legacy score fallbacks."""
    info = _pick(information_completeness, completeness_score)
    evidence = _pick(evidence_confidence, evidence_ratio)
    constraint = _pick(constraint_understanding, max(0.0, 1.0 - assumption_ratio))
    intent = _pick(
        design_intent_clarity,
        max(0.25, completeness_score * 0.45 + (1.0 - assumption_ratio) * 0.35),
    )
    alignment = _pick(user_alignment, 0.35 + intent * 0.25)
    research = research_need
    if research is None:
        research = derive_research_need(
            information_completeness=info,
            evidence_confidence=evidence,
            constraint_understanding=constraint,
        )
    else:
        research = max(
            _clamp(research),
            derive_research_need(
                information_completeness=info,
                evidence_confidence=evidence,
                constraint_understanding=constraint,
            )
            * 0.35,
        )
    return KnowledgeDimensions(
        information_completeness=info,
        design_intent_clarity=intent,
        evidence_confidence=evidence,
        constraint_understanding=constraint,
        user_alignment=alignment,
        research_need=_clamp(research),
    )


def dimensions_from_rule_signals(
    *,
    user_text: str,
    evidence: ProjectEvidencePack,
    evidence_ratio: float,
) -> KnowledgeDimensions:
    """Deterministic multi-axis estimate for rule fallback / no-LLM path."""
    text = user_text or ""
    info = min(
        0.92,
        0.08
        + evidence.document_count * 0.12
        + evidence.confirmed_fact_count * 0.12
        + evidence.extracted_fact_count * 0.05
        + evidence.knowledge_item_count * 0.04,
    )
    if evidence.document_count >= 2:
        info = max(info, 0.5)
    if evidence.confirmed_fact_count >= 2:
        info = max(info, 0.55)
    evidence_conf = _clamp(max(evidence_ratio, min(0.85, evidence.document_count * 0.12)))

    intent_hits = sum(
        1
        for token in (
            "概念",
            "意境",
            "氛围",
            "空间",
            "礼仪",
            "仪式",
            "轴线",
            "庭院",
            "叙事",
            "体验",
            "愿景",
            "策略",
            "形式",
            "材料",
            "寺庙",
            "禅",
            "礼佛",
        )
        if token in text
    )
    intent = _clamp(0.2 + intent_hits * 0.12 + (0.15 if len(text) > 80 else 0.0))
    # Sparse materials + strong language → high intent (temple case)
    if info < 0.35 and intent_hits >= 2:
        intent = max(intent, 0.7)

    constraint = _clamp(
        0.1
        + evidence.confirmed_fact_count * 0.1
        + (0.15 if evidence.blocking_gap_count == 0 and evidence.has_evidence else 0.0)
        + (0.1 if any(t in text for t in ("红线", "规范", "限高", "文保", "消防")) else 0.0)
    )
    alignment = _clamp(
        0.3
        + (0.2 if any(t in text for t in ("甲方", "业主", "使用者", "僧众", "游客")) else 0.0)
        + intent * 0.25
    )
    research = derive_research_need(
        information_completeness=info,
        evidence_confidence=evidence_conf,
        constraint_understanding=constraint,
    )
    if any(t in text for t in ("研究", "案例", "类型", "历史", "典故", "规制")):
        research = max(research, 0.65)
    return KnowledgeDimensions(
        information_completeness=info,
        design_intent_clarity=intent,
        evidence_confidence=evidence_conf,
        constraint_understanding=constraint,
        user_alignment=alignment,
        research_need=research,
    )


def apply_dimensions_to_state(
    state: KnowledgeState,
    dimensions: KnowledgeDimensions,
) -> KnowledgeState:
    return state.model_copy(update={"dimensions": dimensions}).with_synced_legacy_scores()


def _pick(primary: float | None, fallback: float) -> float:
    if primary is None:
        return _clamp(fallback)
    return _clamp(primary)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
