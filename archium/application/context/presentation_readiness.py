"""Presentation-stage readiness derived from ProjectContext (not RAG bundles)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from archium.application.knowledge_gap_detection import filter_unknowns_satisfied_by_known
from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.next_best_action import NextBestActionType


class PresentationGateVerdict(StrEnum):
    """How Narrative generation should treat current cognition."""

    PROCEED = "proceed"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class PresentationContextReadiness:
    """CI surface for generate / presentation entry (warn / block / proceed)."""

    has_context: bool
    completeness_pct: int = 0
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    recommended_workflow: RecommendedWorkflow | None = None
    lifecycle_label: str = ""
    verdict: PresentationGateVerdict = PresentationGateVerdict.WARN
    suggested_action: NextBestActionType | None = None
    suggested_action_reason: str = ""

    @property
    def blocks_generation(self) -> bool:
        return self.verdict == PresentationGateVerdict.BLOCK

    def as_dict(self) -> dict[str, object]:
        return {
            "has_context": self.has_context,
            "completeness_pct": self.completeness_pct,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "recommended_workflow": (
                self.recommended_workflow.value if self.recommended_workflow else None
            ),
            "lifecycle_label": self.lifecycle_label,
            "verdict": self.verdict.value,
            "suggested_action": (
                self.suggested_action.value if self.suggested_action else None
            ),
            "suggested_action_reason": self.suggested_action_reason,
        }


def _suggest_from_presentation_policy(
    *,
    context: ProjectContext | None,
    completeness_pct: int,
    unknowns: list[str],
    workflow: RecommendedWorkflow | None,
) -> tuple[NextBestActionType | None, str]:
    from archium.application.context.knowledge_vector_policy import (
        actions_for_presentation_entry,
    )

    vector = None
    blocking = False
    if context is not None and context.knowledge_state is not None:
        state = context.knowledge_state
        vector = state.effective_dimensions()
        blocking = any(g.blocking for g in (state.open_unknowns or []))

    actions = actions_for_presentation_entry(
        vector,
        completeness_pct=completeness_pct,
        unknown_count=len(unknowns),
        recommended_workflow=workflow,
        blocking_gaps=blocking,
    )
    if not actions:
        return None, ""
    top = actions[0]
    return top.action, top.reason


def _verdict_for(
    *,
    has_context: bool,
    completeness_pct: int,
    unknowns: list[str],
    workflow: RecommendedWorkflow | None,
) -> PresentationGateVerdict:
    if not has_context:
        return PresentationGateVerdict.WARN
    if completeness_pct < 25:
        return PresentationGateVerdict.BLOCK
    soft_workflows = {
        RecommendedWorkflow.RESEARCH,
        RecommendedWorkflow.EXPLORE,
        RecommendedWorkflow.MATERIALS,
    }
    if completeness_pct < 45 or unknowns or workflow in soft_workflows:
        return PresentationGateVerdict.WARN
    return PresentationGateVerdict.PROCEED


def presentation_readiness_from_context(
    context: ProjectContext | None,
) -> PresentationContextReadiness:
    """Map ProjectContext into gate verdict + warnings for Narrative entry."""
    if context is None or context.knowledge_state is None:
        suggested, reason = _suggest_from_presentation_policy(
            context=None,
            completeness_pct=0,
            unknowns=[],
            workflow=RecommendedWorkflow.MATERIALS,
        )
        return PresentationContextReadiness(
            has_context=False,
            summary="尚未评估项目知识状态",
            warnings=[
                "尚未建立 ProjectContext；汇报可能偏假设。"
                "建议先在「开始项目」或任务页刷新知识状态。"
            ],
            verdict=PresentationGateVerdict.WARN,
            suggested_action=suggested or NextBestActionType.UPLOAD_MATERIALS,
            suggested_action_reason=reason
            or "尚未建立知识状态，先补资料再评估",
        )

    state = context.knowledge_state
    completeness_pct = int(round(max(0.0, min(1.0, state.completeness_score)) * 100))
    workflow = context.recommended_workflow
    warnings: list[str] = []

    if completeness_pct < 25:
        warnings.append(
            f"知识完整度约 {completeness_pct}%：建议先澄清或补充研究，再作正式汇报。"
        )
    elif completeness_pct < 45:
        warnings.append(
            f"知识完整度约 {completeness_pct}%：可出概念草稿，正式交付前建议补证据。"
        )

    unknowns = filter_unknowns_satisfied_by_known(
        [u.strip() for u in (state.unknown or []) if str(u).strip()],
        known=state.known,
    )
    if unknowns:
        preview = "、".join(unknowns[:3])
        suffix = "…" if len(unknowns) > 3 else ""
        warnings.append(f"仍有未知项：{preview}{suffix}")

    if workflow == RecommendedWorkflow.EXPLORE:
        warnings.append("当前更建议先推演概念方向，再进入汇报主链。")
    elif workflow == RecommendedWorkflow.RESEARCH:
        warnings.append("当前更建议补充背景研究，再进入汇报主链。")
    elif workflow == RecommendedWorkflow.MATERIALS:
        warnings.append("当前更建议整理资料 / 确认事实，再进入汇报主链。")

    verdict = _verdict_for(
        has_context=True,
        completeness_pct=completeness_pct,
        unknowns=unknowns,
        workflow=workflow,
    )
    suggested, reason = _suggest_from_presentation_policy(
        context=context,
        completeness_pct=completeness_pct,
        unknowns=unknowns,
        workflow=workflow,
    )
    if reason and verdict != PresentationGateVerdict.PROCEED:
        warnings.append(reason)

    summary = (
        f"知识完整度约 {completeness_pct}%"
        f" · 阶段 {context.lifecycle_stage.value}"
        f" · 建议优先 {workflow.value}"
        f" · 门禁 {verdict.value}"
    )
    return PresentationContextReadiness(
        has_context=True,
        completeness_pct=completeness_pct,
        summary=summary,
        warnings=warnings,
        recommended_workflow=workflow,
        lifecycle_label=context.lifecycle_stage.value,
        verdict=verdict,
        suggested_action=suggested,
        suggested_action_reason=reason,
    )


def format_readiness_for_prompt(readiness: PresentationContextReadiness) -> str:
    """Compact cognition note for Narrative LLM context (not a second RAG pass)."""
    lines = [f"【知识完备性】{readiness.summary}"]
    if readiness.suggested_action is not None:
        lines.append(f"建议下一步动作：{readiness.suggested_action.value}")
        if readiness.suggested_action_reason:
            lines.append(f"原因：{readiness.suggested_action_reason}")
    for warning in readiness.warnings[:5]:
        lines.append(f"- {warning}")
    return "\n".join(lines)
