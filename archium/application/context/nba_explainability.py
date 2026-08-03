"""Fill explainable NBA fields from action type when producers omit them."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType

# Catalog: (affects, expected_outcome, reversible)
_CATALOG: dict[NextBestActionType, tuple[list[str], str, bool | None]] = {
    NextBestActionType.ASK: (
        ["待核实事实", "可能影响项目概况与指标相关页面"],
        "澄清冲突或缺口后，相关页面可按确认结果再生成。",
        True,
    ),
    NextBestActionType.UPLOAD_MATERIALS: (
        ["项目资料库", "事实台账"],
        "新资料进入解析与事实提取，知识状态会刷新。",
        True,
    ),
    NextBestActionType.RESEARCH: (
        ["研究笔记", "背景参照"],
        "补齐公开背景与类型参照，供任务理解与方向推演使用。",
        True,
    ),
    NextBestActionType.EXPLORE_DIRECTIONS: (
        ["概念方向", "方案假设"],
        "得到可比较的方向草案，不直接改正式汇报页。",
        True,
    ),
    NextBestActionType.GENERATE_MISSION: (
        ["项目任务理解", "汇报目标边界"],
        "生成或更新任务陈述，供大纲与生成引用。",
        True,
    ),
    NextBestActionType.OPEN_MISSION: (
        ["项目任务页"],
        "打开已有任务理解以便查看或微调。",
        True,
    ),
}


@dataclass(frozen=True, slots=True)
class ExplainableNbaCard:
    """View model for one explainable next-step card."""

    action: NextBestActionType
    title: str
    why_now: str
    affects: tuple[str, ...]
    expected_outcome: str
    reversible_label: str
    question: str | None = None


def enrich_next_best_action(action: NextBestAction) -> NextBestAction:
    """Return a copy with explainability gaps filled from the catalog."""
    affects_default, outcome_default, reversible_default = _CATALOG.get(
        action.action,
        (["当前项目上下文"], "推进当前建议步骤。", None),
    )
    why = (action.why_now or action.reason or "").strip()
    if not why:
        why = "根据当前知识状态，这是优先建议的下一步。"
    affects = list(action.affects) if action.affects else list(affects_default)
    outcome = (action.expected_outcome or "").strip() or outcome_default
    reversible = action.reversible if action.reversible is not None else reversible_default
    return action.model_copy(
        update={
            "why_now": why,
            "reason": action.reason or why,
            "affects": affects,
            "expected_outcome": outcome,
            "reversible": reversible,
        }
    )


def enrich_next_best_actions(actions: list[NextBestAction]) -> list[NextBestAction]:
    return [enrich_next_best_action(item) for item in actions]


def reversible_label(reversible: bool | None) -> str:
    if reversible is True:
        return "可以撤销或回退（工作室编辑可撤销；事实确认可再改）"
    if reversible is False:
        return "此步骤通常不可自动撤销，请确认后再执行"
    return "视具体操作而定；工作室内的页面编辑一般可撤销"


def build_explainable_nba_card(
    action: NextBestAction,
    *,
    title: str = "",
) -> ExplainableNbaCard:
    """Pure helper for UI / tests — always returns a complete card."""
    enriched = enrich_next_best_action(action)
    label = (title or "").strip()
    if not label:
        from archium.application.context.nba_action_executor import nba_execute_label

        label = nba_execute_label(
            enriched.action,
            reason=enriched.reason,
        ) or enriched.action.value
    return ExplainableNbaCard(
        action=enriched.action,
        title=label,
        why_now=enriched.why_now,
        affects=tuple(enriched.affects),
        expected_outcome=enriched.expected_outcome,
        reversible_label=reversible_label(enriched.reversible),
        question=enriched.question,
    )
