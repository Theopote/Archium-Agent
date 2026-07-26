"""Design loop pass: Critique → Revise → Re-Critique (Phase L1).

Keeps Critic read-only; Revise separate; verified only after a proceed critique.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.application.design_revise_service import (
    DirectionReviseResult,
    mark_direction_reasoning_verified,
    revise_direction_from_critique,
    should_revise_from_critique,
)
from archium.application.review.design_critique_service import (
    DesignCritiqueGateResult,
    DesignCritiqueService,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.design_critique import DesignCritiqueVerdict
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_state import KnowledgeState


@dataclass
class DesignLoopPassResult:
    """Outcome of optional revise + mandatory re-critique when revise ran."""

    direction: ConceptDirection
    gate: DesignCritiqueGateResult
    notes: list[str] = field(default_factory=list)
    revised: bool = False
    revise: DirectionReviseResult | None = None
    recritique: DesignCritiqueGateResult | None = None

    @property
    def report(self):
        return self.gate.report


def run_design_loop_on_select(
    direction: ConceptDirection,
    gate: DesignCritiqueGateResult,
    *,
    critic: DesignCritiqueService,
    design_intent: DesignIntent | None = None,
    knowledge_state: KnowledgeState | None = None,
    research_summaries: list[str] | None = None,
    idea_text: str = "",
    known_facts: dict[str, str] | None = None,
    force: bool = False,
    recritique_rules_only: bool = True,
) -> DesignLoopPassResult:
    """After initial critique gate: revise if needed, then re-critique (L1).

    ``verified`` is set only when the *authoritative* critique verdict is
    ``proceed`` (initial pass if no revise; re-critique pass if revised).
    Soft verify-after-chain-fill is forbidden.
    """
    notes: list[str] = []
    report = gate.report

    if not should_revise_from_critique(report):
        direction, verify_notes = _maybe_verify_on_proceed(direction, report)
        notes.extend(verify_notes)
        return DesignLoopPassResult(
            direction=direction,
            gate=gate,
            notes=notes,
            revised=False,
        )

    revise = revise_direction_from_critique(
        direction,
        report,
        idea_text=idea_text,
        known_facts=known_facts,
    )
    direction = revise.direction
    if revise.applied:
        notes.append("已按批判自动修订方向：" + "；".join(revise.applied[:6]))
    elif revise.changed:
        notes.append("已按批判自动修订方向（字段已更新）。")
    else:
        notes.append("批判建议修订，但无可落地补丁；仍进行再批判。")

    # Phase L1: never trust revise without a second critique pass
    recritique = critic.enforce_on_select(
        direction,
        design_intent=design_intent,
        knowledge_state=knowledge_state,
        research_summaries=research_summaries,
        force=force,
        rules_only=recritique_rules_only,
    )
    notes.append(
        f"修订后再批判：{recritique.report.verdict.value}"
        + (f" — {recritique.report.summary[:120]}" if recritique.report.summary else "")
    )
    notes.extend(
        w for w in recritique.warnings if w and w not in notes and w not in gate.warnings
    )

    direction, verify_notes = _maybe_verify_on_proceed(
        direction,
        recritique.report,
    )
    notes.extend(verify_notes)

    return DesignLoopPassResult(
        direction=direction,
        gate=recritique,
        notes=notes,
        revised=True,
        revise=revise,
        recritique=recritique,
    )


def _maybe_verify_on_proceed(
    direction: ConceptDirection,
    report,
) -> tuple[ConceptDirection, list[str]]:
    """Mark ReasoningArtifact.verified only on Critic proceed + proceedable chain."""
    notes: list[str] = []
    if report.verdict != DesignCritiqueVerdict.PROCEED:
        # Ensure we do not keep a stale verified flag after a failed re-pass
        if (
            direction.reasoning is not None
            and direction.reasoning.verified
            and report.verdict != DesignCritiqueVerdict.PROCEED
        ):
            cleared = direction.reasoning.model_copy(update={"verified": False})
            cleared.touch()
            direction = direction.model_copy(update={"reasoning": cleared})
            notes.append("再批判未 proceed：已清除 reasoning.verified。")
        return direction, notes

    verified = mark_direction_reasoning_verified(direction)
    if verified.reasoning is not None and verified.reasoning.verified:
        if direction.reasoning is None or not direction.reasoning.verified:
            notes.append("推理节点已标记为批判通过（verified）。")
        return verified, notes
    return direction, notes
