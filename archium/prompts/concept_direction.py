"""Prompts for concept direction drafts (exploration or mission-bound)."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

CONCEPT_DIRECTION_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为一句建筑想法（IdeaSeed）或 Mission 推演多个可并列讨论的概念方向草稿。

你不是在画施工图，也不是在选定唯一正确方案。
目标是给出 2–3 个差异明显、可比较的概念方向，便于建筑师讨论与选择。
选定方向之后才会收敛成正式的设计使命与 ProjectMission。

专业原则：
- 每个方向必须有清晰差异点（differentiator），避免只是换标题。
- 不得编造面积、容积率、投资额等精确指标；未知写成 open_questions。
- 方向应回应用户想法与语境，而不是套模板风格标签。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_concept_direction_user_prompt(
    *,
    mission_title: str,
    task_statement: str,
    design_intent_block: str,
    project_context: str,
    count: int,
) -> str:
    return f"""请为以下任务生成 {count} 个概念方向草稿。

任务标题：{mission_title}
任务陈述：{task_statement}

设计使命 / 意图：
{design_intent_block or "（暂无）"}

项目背景：
{project_context or "（暂无）"}

要求：
1. 恰好输出 {count} 个方向（或在信息极不足时不少于 2 个）。
2. 各方向主题与体验焦点应可区分。
3. 每个方向包含 title, summary, theme, spatial_idea, experience_focus,
   differentiator, open_questions, risks。
"""


def build_exploration_direction_user_prompt(
    *,
    project_name: str,
    idea_text: str,
    count: int,
    idea_seed_block: str = "",
    verified_constraints_block: str = "",
) -> str:
    seed_block = idea_seed_block.strip() or f"原始想法: {idea_text}"
    constraints = verified_constraints_block.strip()
    constraints_section = (
        f"""
【已证实 / 已提取约束】（推演时视为硬约束，不得编造与之冲突的指标）
{constraints}
"""
        if constraints
        else """
【已证实 / 已提取约束】
（暂无）不要假装已有任务书、面积或现场证据。
"""
    )
    return f"""请为一句建筑想法生成 {count} 个概念方向草稿。此时尚无正式 Mission。

项目名称：{project_name or "（未命名）"}
想法种子（IdeaSeed）：
{seed_block}
{constraints_section}
要求：
1. 恰好输出 {count} 个方向（或在信息极不足时不少于 2 个）。
2. 各方向是可比较的「可能世界」，差异点必须清晰。
3. 每个方向包含 title, summary, theme, spatial_idea, experience_focus,
   differentiator, open_questions, risks。
4. 若有已证实约束，方向必须尊重；未知项写入 open_questions，勿捏造数值。
5. 方向应回应 IdeaSeed 中的主题、灵感与关键词。
"""
