"""Presentation-stage readiness derived from ProjectContext (not RAG bundles)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.intent.next_best_action import NextBestActionType


class PresentationGateVerdict(StrEnum):
    """How Narrative generation should treat current cognition."""

    PROCEED = "proceed"
    WARN = "warn"
    BLOCK = "block"


_WORKFLOW_TO_ACTION: dict[RecommendedWorkflow, NextBestActionType] = {
    RecommendedWorkflow.RESEARCH: NextBestActionType.RESEARCH,
    RecommendedWorkflow.EXPLORE: NextBestActionType.EXPLORE_DIRECTIONS,
    RecommendedWorkflow.MATERIALS: NextBestActionType.UPLOAD_MATERIALS,
    RecommendedWorkflow.MISSION: NextBestActionType.OPEN_MISSION,
}


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
        }


def _suggest_action(
    *,
    workflow: RecommendedWorkflow | None,
    unknowns: list[str],
) -> NextBestActionType | None:
    if workflow is not None and workflow in _WORKFLOW_TO_ACTION:
        return _WORKFLOW_TO_ACTION[workflow]
    if unknowns:
        return NextBestActionType.ASK
    return None


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
        return PresentationContextReadiness(
            has_context=False,
            summary="尚未评估项目知识状态",
            warnings=[
                "尚未建立 ProjectContext；汇报可能偏假设。"
                "建议先在「开始项目」或任务页刷新知识状态。"
            ],
            verdict=PresentationGateVerdict.WARN,
            suggested_action=NextBestActionType.UPLOAD_MATERIALS,
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

    unknowns = [u.strip() for u in (state.unknown or []) if str(u).strip()]
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
    suggested = _suggest_action(workflow=workflow, unknowns=unknowns)

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
    )


def format_readiness_for_prompt(readiness: PresentationContextReadiness) -> str:
    """Compact cognition note for Narrative LLM context (not a second RAG pass)."""
    lines = [f"【知识完备性】{readiness.summary}"]
    if readiness.suggested_action is not None:
        lines.append(f"建议下一步动作：{readiness.suggested_action.value}")
    for warning in readiness.warnings[:5]:
        lines.append(f"- {warning}")
    return "\n".join(lines)
