"""Design loop pass: Critique → (Ask|Auto) Revise → Re-Critique (L1+L2).

Keeps Critic read-only; Revise separate; verified only after a proceed critique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

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
from archium.domain.design_critique import DesignCritiqueReport, DesignCritiqueVerdict
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.knowledge_state import KnowledgeState

ReviseMode = Literal["off", "auto", "ask"]
ReviseAction = Literal["apply", "reject"]
RevisePolicy = Literal["off", "auto", "ask", "apply", "reject"]


@dataclass
class DesignReviseOffer:
    """Pending Critic→Revise decision for Ask mode (not yet persisted)."""

    direction_id: UUID
    project_id: UUID
    critique_report: DesignCritiqueReport
    revise_preview: DirectionReviseResult
    mode: str = "ask"

    def as_dict(self) -> dict[str, object]:
        reflection = self.revise_preview.reflection
        return {
            "direction_id": str(self.direction_id),
            "project_id": str(self.project_id),
            "mode": self.mode,
            "critique": self.critique_report.as_dict(),
            "revise": self.revise_preview.as_dict(),
            "diff_lines": self.diff_lines(),
            "next_adjustments": list(
                reflection.next_adjustments if reflection is not None else []
            ),
            "reflection": reflection.as_dict() if reflection is not None else None,
        }

    def diff_lines(self) -> list[str]:
        lines: list[str] = []
        for item in self.revise_preview.applied[:10]:
            lines.append(f"将应用：{item}")
        reflection = self.revise_preview.reflection
        if reflection is not None:
            for adj in reflection.next_adjustments[:6]:
                text = (adj or "").strip()
                if text and f"将应用：{text}" not in lines:
                    lines.append(f"调整建议：{text}")
        if not lines and self.revise_preview.changed:
            lines.append("方向字段将按批判补丁更新（链 / 风险 / 开放问题）。")
        if not lines:
            lines.append("批判建议修订，但预览未产生可展示补丁。")
        return lines


@dataclass
class DesignLoopPassResult:
    """Outcome of optional revise + mandatory re-critique when revise ran."""

    direction: ConceptDirection
    gate: DesignCritiqueGateResult
    notes: list[str] = field(default_factory=list)
    revised: bool = False
    revise: DirectionReviseResult | None = None
    recritique: DesignCritiqueGateResult | None = None
    pending_offer: DesignReviseOffer | None = None

    @property
    def report(self) -> DesignCritiqueReport:
        return self.gate.report

    @property
    def awaiting_user(self) -> bool:
        return self.pending_offer is not None


def resolve_revise_policy(
    mode: str | None,
    revise_action: str | None = None,
) -> RevisePolicy:
    """Map settings mode + optional UI action to an execution policy."""
    resolved = (mode or "ask").strip().lower()
    if resolved not in {"off", "auto", "ask"}:
        resolved = "ask"
    action = (revise_action or "").strip().lower()
    if action in {"apply", "reject"}:
        return action  # type: ignore[return-value]
    return resolved  # type: ignore[return-value]


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
    revise_policy: RevisePolicy = "auto",
) -> DesignLoopPassResult:
    """After initial critique gate: revise per policy, then re-critique when applied.

    Policies:
    - ``off`` / ``reject``: never revise; verify on initial gate
    - ``ask``: if revise needed, return ``pending_offer`` (no DB write)
    - ``auto`` / ``apply``: revise + re-critique (L1)
    """
    notes: list[str] = []
    report = gate.report

    if revise_policy in {"off", "reject"}:
        if revise_policy == "reject" and should_revise_from_critique(report):
            notes.append("已拒绝批判修订补丁；按原方向继续选定。")
        direction, verify_notes = _maybe_verify_on_proceed(direction, report)
        notes.extend(verify_notes)
        return DesignLoopPassResult(
            direction=direction,
            gate=gate,
            notes=notes,
            revised=False,
        )

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

    if revise_policy == "ask":
        offer = DesignReviseOffer(
            direction_id=direction.id,
            project_id=direction.project_id,
            critique_report=report,
            revise_preview=revise,
            mode="ask",
        )
        notes.append(
            "批判建议修订方向：请确认应用补丁，或拒绝后按原方向选定。"
        )
        notes.extend(offer.diff_lines()[:6])
        return DesignLoopPassResult(
            direction=direction,
            gate=gate,
            notes=notes,
            revised=False,
            revise=revise,
            pending_offer=offer,
        )

    # auto / apply
    direction = revise.direction
    if revise.applied:
        notes.append("已按批判自动修订方向：" + "；".join(revise.applied[:6]))
    elif revise.changed:
        notes.append("已按批判自动修订方向（字段已更新）。")
    else:
        notes.append("批判建议修订，但无可落地补丁；仍进行再批判。")

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
    report: DesignCritiqueReport,
) -> tuple[ConceptDirection, list[str]]:
    """Mark ReasoningArtifact.verified only on Critic proceed + proceedable chain."""
    notes: list[str] = []
    if report.verdict != DesignCritiqueVerdict.PROCEED:
        if (
            direction.reasoning is not None
            and direction.reasoning.verified
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
