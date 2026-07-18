"""Prompts for clarification-driven mission revision."""

from __future__ import annotations

from archium.prompts.project_mission import MISSION_SYSTEM_PROMPT

CLARIFICATION_REVISION_SYSTEM_PROMPT = MISSION_SYSTEM_PROMPT + """\
本轮是在用户回答关键问题或接受假设之后修订任务理解。

修订原则：
- 将用户答案写入任务陈述、范围、约束或决策需求中，不得忽略。
- 已接受的假设必须写入 assumptions 并在 known_constraints 中以 inferred/assumption 标记。
- 仍未回答且非阻塞的问题可保留在 key_unknowns。
- 已回答的 knowledge_gaps / clarifying_questions 不要重复生成；clarifying_questions 可返回空列表。
- 不得虚构面积、用地、高度、预算或规范条件。
"""


def build_clarification_revision_prompt(
    *,
    current_mission_json: str,
    clarification_summary: str,
    project_context: str,
    fact_ledger_summary: str,
) -> str:
    return (
        "请根据澄清结果修订 ProjectMission JSON。\n\n"
        f"【当前任务理解】\n{current_mission_json}\n\n"
        f"【澄清结果】\n{clarification_summary}\n\n"
        f"【项目资料】\n{project_context.strip() or '暂无资料'}\n\n"
        f"【项目事实账本】\n{fact_ledger_summary.strip() or '暂无已提取事实'}\n\n"
        "将已确认答案并入任务理解；未回答的非阻塞问题可继续保留为未知。"
        "clarifying_questions 与 knowledge_gaps 可返回空列表（已有澄清记录将保留）。"
    )
