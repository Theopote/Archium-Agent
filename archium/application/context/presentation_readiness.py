"""Presentation-stage readiness derived from ProjectContext (not RAG bundles)."""

from __future__ import annotations

from dataclasses import dataclass, field

from archium.domain.context.project_context import ProjectContext
from archium.domain.context.recommended_workflow import RecommendedWorkflow


@dataclass(frozen=True)
class PresentationContextReadiness:
    """Lightweight CI surface for generate / presentation entry."""

    has_context: bool
    completeness_pct: int = 0
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    recommended_workflow: RecommendedWorkflow | None = None
    lifecycle_label: str = ""


def presentation_readiness_from_context(
    context: ProjectContext | None,
) -> PresentationContextReadiness:
    """Map ProjectContext into warnings the generate page can show before pipeline run."""
    if context is None or context.knowledge_state is None:
        return PresentationContextReadiness(
            has_context=False,
            summary="尚未评估项目知识状态",
            warnings=[
                "尚未建立 ProjectContext；汇报可能偏假设。"
                "建议先在「开始项目」或任务页刷新知识状态。"
            ],
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

    summary = (
        f"知识完整度约 {completeness_pct}%"
        f" · 阶段 {context.lifecycle_stage.value}"
        f" · 建议优先 {workflow.value}"
    )
    return PresentationContextReadiness(
        has_context=True,
        completeness_pct=completeness_pct,
        summary=summary,
        warnings=warnings,
        recommended_workflow=workflow,
        lifecycle_label=context.lifecycle_stage.value,
    )
