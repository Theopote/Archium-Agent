"""Prompts for project mission generation."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

MISSION_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：理解用户描述的建筑任务，生成结构化的 ProjectMission 及相关规划对象。

你不是在生成 PPT 大纲，也不是在套用固定项目模板。
项目类型只能作为背景，不得因“医院”“寺庙”“学校”等类型自动假定任务范围。

专业原则：
- 区分 confirmed facts（已确认事实）、reasonable inferences（合理推断）、proposed assumptions（建议假设）、open questions（待解问题）。
- 资料中缺失的信息必须标记为未知，写入 knowledge_gaps 或 key_unknowns。
- 推断必须标记 verification_status 为 inferred；假设写入 assumptions。
- 不得虚构面积、用地、高度、预算或规范条件；无依据时不得写入具体数值。
- 若项目事实账本中已有确认指标，必须在 known_constraints 中保留，不得覆盖或忽略。
- 若事实存在冲突，不得自动选定其中一个版本。

clarifying_questions 首轮最多 5 个，优先询问对任务范围、成果类型、设计方向影响最大的问题。
禁止优先询问低价值细节。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。
- 不要把推断写成已确认条件。

输出必须是合法 JSON，顶层字段包括：
title, task_statement, task_natures, domains, intervention_scales, requested_service_depths,
project_context, current_situation, primary_problems, desired_changes, in_scope, out_of_scope,
stakeholders, decision_context, decisions_required, known_constraints, key_unknowns,
research_questions, design_question_summaries, evaluation_criteria, uncertainty_level, confidence,
knowledge_gaps, assumptions, clarifying_questions, design_questions, design_intent
"""

CONCEPT_MISSION_ADDENDUM = """
【概念探索模式 — 设计使命 v0.1】
- 这是从 0 到 1 的概念探索，不是「生成 N 页 PPT」的任务说明。
- 必须输出 design_intent 对象，包含 theme, problem_statement, social_background,
  cultural_context, target_users, desired_experience, core_questions, research_needed,
  working_assumptions。
- 缺失地点、规模、用户等信息时：写入 assumptions（requires_confirmation=true）和
  design_intent.working_assumptions，并列出 research_questions / research_needed。
- clarifying_questions 最多 3 个，全部 blocking=false，can_assume=true，并提供 suggested_assumption。
- task_statement 应表达设计使命（探索什么问题、创造什么体验），而非交付页数。
"""


def build_concept_mission_addendum() -> str:
    return CONCEPT_MISSION_ADDENDUM


def build_mission_user_prompt(
    *,
    user_task_description: str,
    project_context: str,
    fact_ledger_summary: str,
    project_name: str = "",
    project_type: str = "",
    concept_mode: bool = False,
) -> str:
    header = "请基于以下信息生成 ProjectMission JSON。\n\n"
    meta = ""
    if project_name or project_type:
        meta = f"【项目基础信息】\n名称: {project_name or '未命名'}\n类型: {project_type or 'other'}\n\n"
    mode_hint = ""
    if concept_mode:
        mode_hint = "【模式】概念探索 — 资料可空，优先建立设计使命与假设。\n\n"
    return (
        header
        + mode_hint
        + meta
        + f"【用户任务描述】\n{user_task_description.strip()}\n\n"
        + f"【已导入资料摘要】\n{project_context.strip() or '暂无资料'}\n\n"
        + f"【项目事实账本】\n{fact_ledger_summary.strip() or '暂无已提取事实'}\n\n"
        + "若资料不足，请通过 knowledge_gaps、assumptions 和 design_intent 明确未知项与假设，"
        + "不要编造面积、高度、预算或规范条文。"
    )


def build_mission_regeneration_prompt(
    *,
    current_mission_json: str,
    user_feedback: str,
    project_context: str,
    fact_ledger_summary: str,
) -> str:
    return (
        "请根据用户反馈修订 ProjectMission JSON。\n\n"
        f"【当前任务理解】\n{current_mission_json}\n\n"
        f"【用户反馈】\n{user_feedback.strip()}\n\n"
        f"【项目资料】\n{project_context.strip() or '暂无资料'}\n\n"
        f"【项目事实账本】\n{fact_ledger_summary.strip() or '暂无已提取事实'}\n\n"
        "保持事实、推断、假设分离；不得虚构无依据的指标。"
    )
