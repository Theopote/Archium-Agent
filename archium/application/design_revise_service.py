"""Revise ConceptDirection from DesignCritique / DesignReflection (Phase R3).

Separate from Critic: Critic stays read-only; this Service applies patches.
No ReasoningAgent — rules + existing ensure_* helpers only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.application.design_rationale_fallback import ensure_direction_design_rationale
from archium.application.design_reflection import reflection_from_critique
from archium.application.reasoning_artifact import ensure_direction_reasoning
from archium.application.spatial_design_layer import ensure_direction_spatial_layer
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import DesignCritiqueReport, DesignCritiqueVerdict
from archium.domain.design_rationale import DesignRationale
from archium.domain.design_reflection import DesignReflection


@dataclass
class DirectionReviseResult:
    """Outcome of applying critique / reflection adjustments to a direction."""

    direction: ConceptDirection
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    reflection: DesignReflection | None = None
    changed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "direction_id": str(self.direction.id),
            "changed": self.changed,
            "applied": list(self.applied),
            "skipped": list(self.skipped),
            "reflection": (
                self.reflection.as_dict() if self.reflection is not None else None
            ),
        }


def should_revise_from_critique(report: DesignCritiqueReport | None) -> bool:
    """True when critique left actionable gaps (caution / reject / incomplete chain)."""
    if report is None:
        return False
    if report.chain_incomplete:
        return True
    if report.verdict in {
        DesignCritiqueVerdict.CAUTION,
        DesignCritiqueVerdict.REJECT,
    }:
        return True
    if report.form_only_risk:
        return True
    if report.weaknesses or report.missing_evidence or report.alternative_directions:
        # Soft: only revise when not a clean proceed
        return report.verdict != DesignCritiqueVerdict.PROCEED
    return False


def revise_direction_from_critique(
    direction: ConceptDirection,
    report: DesignCritiqueReport,
    *,
    reflection: DesignReflection | None = None,
    idea_text: str = "",
    known_facts: dict[str, str] | None = None,
) -> DirectionReviseResult:
    """Patch rationale / risks / open_questions / spatial from critique findings.

    Idempotent-ish: fills empty chain slots; appends risk/question lines without
    duplicating exact text. Never invents area/FAR metrics.
    """
    reflection = reflection or reflection_from_critique(report)
    applied: list[str] = []
    skipped: list[str] = []

    before = direction.model_dump(mode="json")
    rationale = direction.design_rationale or DesignRationale()
    risks = list(direction.risks or [])
    open_questions = list(direction.open_questions or [])

    # --- Chain completeness from direction fields + critique ---
    rationale, chain_applied = _fill_reasoning_chain(rationale, direction)
    applied.extend(chain_applied)

    if report.form_only_risk:
        note = "形式风险：论证偏形式语言，需补问题/使用矛盾回应"
        if note not in risks:
            risks.append(note)
            applied.append("risk:form_only")

    for item in report.weaknesses[:6]:
        text = (item.text or "").strip()
        if not text:
            continue
        line = text[:240]
        if line not in risks:
            risks.append(line)
            applied.append(f"risk:weakness:{line[:40]}")

    for item in report.missing_evidence[:6]:
        text = (item.text or "").strip()
        if not text:
            continue
        line = f"待补证据：{text[:200]}"
        if line not in open_questions and text not in open_questions:
            open_questions.append(line)
            applied.append(f"question:evidence:{text[:40]}")

    # Executable reflection.next_adjustments
    for adj in reflection.next_adjustments[:8]:
        text = (adj or "").strip()
        if not text:
            continue
        patch = _apply_adjustment_text(
            text,
            rationale=rationale,
            direction=direction,
            risks=risks,
            open_questions=open_questions,
        )
        if patch.applied:
            rationale = patch.rationale
            risks = patch.risks
            open_questions = patch.open_questions
            applied.extend(patch.applied)
        else:
            skipped.append(text[:120])

    for risk in reflection.top_risks[:4]:
        text = (risk or "").strip()[:240]
        if text and text not in risks:
            risks.append(text)
            applied.append(f"risk:reflection:{text[:40]}")

    direction = direction.model_copy(
        update={
            "design_rationale": None if rationale.is_empty() else rationale,
            "risks": risks[:12],
            "open_questions": open_questions[:12],
        }
    )
    direction = ensure_direction_design_rationale(
        direction,
        known_facts=known_facts,
        idea_text=idea_text,
    )
    direction = ensure_direction_reasoning(direction)
    direction = ensure_direction_spatial_layer(direction)
    # Phase L1: never set verified here — only after a Critic proceed (re)pass.

    after = direction.model_dump(mode="json")
    changed = before != after
    if not changed and not applied:
        skipped.append("无可用调整（批判未产出可落地补丁）")

    return DirectionReviseResult(
        direction=direction,
        applied=applied,
        skipped=skipped,
        reflection=reflection,
        changed=changed,
    )


def mark_direction_reasoning_verified(
    direction: ConceptDirection,
) -> ConceptDirection:
    """Flag proceedable reasoning as Critic-verified (call only after proceed)."""
    direction = ensure_direction_reasoning(direction)
    if direction.reasoning is None or not direction.reasoning.is_proceedable():
        return direction
    if direction.reasoning.verified:
        return direction
    return direction.model_copy(
        update={"reasoning": direction.reasoning.mark_verified()}
    )


def apply_reflection_adjustments(
    direction: ConceptDirection,
    reflection: DesignReflection,
    *,
    idea_text: str = "",
    known_facts: dict[str, str] | None = None,
) -> DirectionReviseResult:
    """Apply DesignReflection.next_adjustments without a full critique report."""
    from archium.domain.design_critique import DesignCritiqueReport

    stub = DesignCritiqueReport(
        direction_id=direction.id,
        project_id=direction.project_id,
        verdict=DesignCritiqueVerdict.CAUTION,
        summary=reflection.why or "应用设计反思调整",
        source="rules",
    )
    return revise_direction_from_critique(
        direction,
        stub,
        reflection=reflection,
        idea_text=idea_text,
        known_facts=known_facts,
    )


@dataclass
class _AdjustmentPatch:
    rationale: DesignRationale
    risks: list[str]
    open_questions: list[str]
    applied: list[str] = field(default_factory=list)


def _fill_reasoning_chain(
    rationale: DesignRationale,
    direction: ConceptDirection,
) -> tuple[DesignRationale, list[str]]:
    applied: list[str] = []
    updates: dict[str, object] = {}
    if not (rationale.problem or "").strip() and (direction.summary or "").strip():
        updates["problem"] = direction.summary.strip()[:300]
        applied.append("chain:problem_from_summary")
    if not (rationale.hypothesis or "").strip():
        hyp = (rationale.statement or direction.theme or direction.title or "").strip()
        if hyp:
            updates["hypothesis"] = hyp[:300]
            applied.append("chain:hypothesis_from_statement")
    if not (rationale.strategy or "").strip():
        strat = (
            direction.spatial_strategy or direction.spatial_idea or ""
        ).strip()
        if strat:
            updates["strategy"] = strat[:300]
            applied.append("chain:strategy_from_spatial")
    if not (rationale.observation or "").strip() and (direction.summary or "").strip():
        # Prefer not to invent observation; only if idea-like summary differs from problem
        pass
    if not updates:
        return rationale, applied
    return rationale.model_copy(update=updates), applied


def _apply_adjustment_text(
    text: str,
    *,
    rationale: DesignRationale,
    direction: ConceptDirection,
    risks: list[str],
    open_questions: list[str],
) -> _AdjustmentPatch:
    """Map a free-text adjustment into structured slots (heuristic)."""
    applied: list[str] = []
    lower = text.casefold()
    updates: dict[str, object] = {}

    if any(token in text for token in ("证据", "缺证", "研究", "补")) and (
        "暂缓" not in text and "带风险继续" not in text
    ):
        line = text[:240]
        if line not in open_questions:
            open_questions = list(open_questions) + [line]
            applied.append(f"question:adj:{line[:40]}")
    elif any(token in text for token in ("风险", "形式", "弱点")):
        line = text[:240]
        if line not in risks:
            risks = list(risks) + [line]
            applied.append(f"risk:adj:{line[:40]}")
    elif any(token in lower for token in ("假设", "hypothesis")) and not (
        rationale.hypothesis or ""
    ).strip():
        updates["hypothesis"] = text[:300]
        applied.append("chain:hypothesis_from_adj")
    elif any(token in text for token in ("策略", "空间")) and not (
        rationale.strategy or ""
    ).strip():
        updates["strategy"] = text[:300]
        applied.append("chain:strategy_from_adj")
    elif any(token in text for token in ("问题", "矛盾")) and not (
        rationale.problem or ""
    ).strip():
        updates["problem"] = text[:300]
        applied.append("chain:problem_from_adj")
    else:
        # Default: keep as actionable open question (executable trail)
        line = f"调整：{text[:220]}"
        if line not in open_questions and text not in open_questions:
            open_questions = list(open_questions) + [line]
            applied.append(f"question:adj_default:{text[:40]}")

    if updates:
        rationale = rationale.model_copy(update=updates)

    return _AdjustmentPatch(
        rationale=rationale,
        risks=risks,
        open_questions=open_questions,
        applied=applied,
    )
