"""Build DesignReflection from Context / Critique (deterministic, no new Agent)."""

from __future__ import annotations

from archium.domain.context.project_context import ProjectContext
from archium.domain.design_critique import DesignCritiqueReport
from archium.domain.design_reflection import DesignReflection


def reflection_from_context(context: ProjectContext) -> DesignReflection:
    state = context.knowledge_state
    assumptions = [str(item) for item in list(context.assumptions)[:6] if str(item).strip()]
    unknowns = [str(item) for item in list(state.unknown or [])[:6] if str(item).strip()]
    if not unknowns and state.missing_information:
        unknowns = [
            str(item) for item in list(state.missing_information)[:6] if str(item).strip()
        ]
    risks = [f"未知未闭合：{item}" for item in unknowns[:3]]
    next_adj: list[str] = []
    for action in context.next_actions[:4]:
        reason = getattr(action, "reason", None)
        label = str(reason).strip() if reason else str(getattr(action, "action", ""))
        if label:
            next_adj.append(label[:200])
    why = context.understanding_summary.strip() or state.summary_line()
    return DesignReflection(
        why=why[:400],
        unverified_assumptions=assumptions,
        top_risks=risks,
        next_adjustments=next_adj,
        source="context",
    )


def reflection_from_critique(report: DesignCritiqueReport) -> DesignReflection:
    why = report.summary.strip() or f"批评裁决：{report.verdict.value}"
    unverified = [item.text for item in report.missing_evidence[:6]]
    risks = [item.text for item in report.weaknesses[:6]]
    if report.form_only_risk:
        risks = ["形式风险偏高：论证偏形式语言"] + risks
    next_adj = [item.text for item in report.alternative_directions[:4]]
    if report.verdict.value == "reject":
        next_adj = ["暂缓固化方向，先补证据或换路径"] + next_adj
    elif report.verdict.value == "caution":
        next_adj = ["带风险继续：先回应弱点与缺证"] + next_adj
    return DesignReflection(
        why=why[:400],
        unverified_assumptions=unverified,
        top_risks=risks,
        next_adjustments=next_adj,
        source="critique",
    )


def reflection_after_research(context: ProjectContext | None) -> DesignReflection | None:
    if context is None:
        return None
    reflection = reflection_from_context(context)
    if reflection.is_empty():
        return None
    return reflection.model_copy(update={"source": "research"})
