"""Prompts for concept direction drafts (exploration or mission-bound).

PROMPT_VERSION history
----------------------
concept_direction.v1 — initial field-oriented instructions
concept_direction.v2 — inject Architectural Reasoning Framework + quality criteria
concept_direction.v3 — inject DesignKnowledge block into user prompts
concept_direction.v4 — reference_case_ids + ArchitectureCase hard links
concept_direction.v5 — Step → design_rationale chain (observation→strategy); card fields as expression
"""

from __future__ import annotations

from archium.prompts.frameworks.architectural_reasoning import (
    ARCHITECTURAL_REASONING_FRAMEWORK,
)
from archium.prompts.identity import ARCHIUM_IDENTITY

PROMPT_VERSION = "concept_direction.v5"

CONCEPT_DIRECTION_SYSTEM_PROMPT = (
    ARCHIUM_IDENTITY
    + """\
当前任务：为一句建筑想法（IdeaSeed）或 Mission 推演多个可并列讨论的概念方向草稿。

你不是在画施工图，也不是在选定唯一正确方案。
目标是给出 2–3 个差异明显、可比较的概念方向，便于建筑师讨论与选择。
选定方向之后才会收敛成正式的设计使命与 ProjectMission。

"""
    + ARCHITECTURAL_REASONING_FRAMEWORK
    + """
字段映射（推理步骤 → design_rationale 链；方向卡片字段为表达层）：
- Step 1 语境 → design_rationale.observation（已知条件/场地/文化观察）；可选 interpretation（观察对设计意味着什么）。
- Step 2 问题 → design_rationale.problem（必须点出回应的矛盾或缺位）；summary 用一句话复述该问题，禁止只写建筑类型名。
- Step 3 意图 → design_rationale.hypothesis + statement（可讨论主张）；theme / experience_focus / differentiator 为表达层。
- Step 4 空间 → design_rationale.strategy（组织逻辑）；spatial_strategy / spatial_idea 与 strategy 一致但可更具体——二者不得互相复读空话。
- Step 5 表达 → formal_language, material_strategy, visual_prompt（服务于 problem/strategy，禁止先行漂亮方案）。
- Step 6 验证 → design_rationale.risks / evidence / alternatives；方向级 risks, open_questions 可并列。
- reference_dna：2–4 条参照基因（类型、氛围、构造传统），不是抄袭具体方案。
- reference_case_ids：可选，填已知案例库 id（如 ningbo_museum、therme_vals、terrace_settlement）；不确定可留空。
- design_rationale 必填链：observation、problem、hypothesis、strategy；另写 reasons（2–4）、evidence（引用用户/资料，勿捏造）、confidence（0–1）、alternatives（1–2）；interpretation 可选。
- visual_prompt：image_prompt（可英中混合）、camera、style；勿写面积等精确指标。
- 不得编造面积、容积率、投资额等精确指标；未知写成 open_questions。
- 方向应回应用户想法与语境，而不是套模板风格标签。
- spatial_strategy、formal_language、risks 不得留空；design_rationale.problem / strategy 不得留空；空字段视为不合格输出。
- 输出合法 JSON，字段与 schema 一致。
"""
)


def build_concept_direction_user_prompt(
    *,
    mission_title: str,
    task_statement: str,
    design_intent_block: str,
    project_context: str,
    count: int,
    design_knowledge_block: str = "",
) -> str:
    knowledge_section = ""
    if design_knowledge_block.strip():
        knowledge_section = f"\n{design_knowledge_block.strip()}\n"
    return f"""请按【建筑推理框架】为以下任务生成 {count} 个概念方向草稿。

任务标题：{mission_title}
任务陈述：{task_statement}

设计使命 / 意图：
{design_intent_block or "（暂无）"}

项目背景：
{project_context or "（暂无）"}
{knowledge_section}
要求：
1. 恰好输出 {count} 个方向（或在信息极不足时不少于 2 个）。
2. 各方向主题与体验焦点应可区分；先写满 design_rationale 推理链（observation→problem→hypothesis→strategy），再写形式。
3. 若有【已沉淀设计知识】，必须把 principle / spatial_translation 转进 design_rationale.strategy 与 spatial_strategy，勿当装饰。
4. 每个方向包含 title, summary, theme, spatial_idea, spatial_strategy,
   formal_language, material_strategy, reference_dna, reference_case_ids,
   visual_prompt, design_rationale, experience_focus, differentiator,
   open_questions, risks。
5. summary 与 design_rationale.problem 须回答「为什么需要这个方向」，不是复述建筑类型。
"""


def build_exploration_direction_user_prompt(
    *,
    project_name: str,
    idea_text: str,
    count: int,
    idea_seed_block: str = "",
    verified_constraints_block: str = "",
    design_knowledge_block: str = "",
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
    knowledge_section = ""
    if design_knowledge_block.strip():
        knowledge_section = f"\n{design_knowledge_block.strip()}\n"
    return f"""请按【建筑推理框架】为一句建筑想法生成 {count} 个概念方向草稿。此时尚无正式 Mission。

项目名称：{project_name or "（未命名）"}
想法种子（IdeaSeed）：
{seed_block}
{constraints_section}{knowledge_section}
要求：
1. 恰好输出 {count} 个方向（或在信息极不足时不少于 2 个）。
2. 各方向是可比较的「可能世界」，差异点必须清晰。
3. 先写满 design_rationale 推理链（observation→problem→hypothesis→strategy），再写形式语言与视觉提示。
4. 若有【已沉淀设计知识】，把可迁移原则落到 design_rationale.strategy / spatial_strategy / material_strategy。
5. 每个方向包含 title, summary, theme, spatial_idea, spatial_strategy,
   formal_language, material_strategy, reference_dna, reference_case_ids,
   visual_prompt, design_rationale, experience_focus, differentiator,
   open_questions, risks。
6. 若有已证实约束，方向必须尊重；未知项写入 open_questions，勿捏造数值。
7. 方向应回应 IdeaSeed 中的主题、灵感与关键词；summary 与 design_rationale.problem 须点出回应的问题。
"""
