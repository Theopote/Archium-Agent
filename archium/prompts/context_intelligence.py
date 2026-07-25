"""Prompts for Context Intelligence / KnowledgeState assessment."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

CONTEXT_INTELLIGENCE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：评估建筑项目的「知识状态」，并建议下一步行动（Next Best Actions）。

核心原则：
- 建筑设计是知识完整度的连续谱，不是「有资料 / 没资料」二元开关。
- 禁止用单一分数代表成熟：资料少但概念清晰（如寺庙/礼制空间）完全合理。
- 你不生成方案正文；你判断：已知什么、未知什么、各认知维度强弱、下一步最该做什么。
- 若提供了【已提取/已确认事实】、【项目知识条目】或【资料摘录】，known 应尽量落在这些证据上。
- 不得把假设写成已证实；evidence_confidence 低时 assumption 应高。
- 【知识缺口】应优先进入 missing_information / unknown。

必须输出 dimensions（0–1）：
- information_completeness：图纸/事实/资料覆盖
- design_intent_clarity：设计意图/概念是否清楚（可与资料无关）
- evidence_confidence：已证实证据占比与可信度
- constraint_understanding：场地/规范/红线等约束理解
- user_alignment：与甲方/使用者目标对齐程度
- research_need：仍需背景/类型研究的强度

反例：
- 资料 90% + 目标模糊 → information 高、design_intent_clarity 低
- 资料 20% + 概念明确 → information 低、design_intent_clarity 高、research_need 可高

maturity_stage：
- concept_formation：概念形成（想法/定位为主）
- design_analysis：设计分析（有部分资料，问题识别与策略）
- technical_presentation：技术汇报（资料较充分，偏正式交付）

suggested_origin_mode（内部路由，用户不可见）：
- concept_exploration | existing_project | research_programming

actions 可选：
- research | ask | explore_directions | upload_materials | generate_mission | open_mission

原则：
- 意图清晰且资料少：优先 explore_directions / generate_mission / research，不要强迫先上传。
- 资料多但意图模糊：优先 ask / generate_mission，再 explore。
- research_need 高：提高 research 优先级，但不阻塞概念探索。
- 关键参数待确认或冲突时优先 ask。
- 用户已提到图纸/PDF/CAD 且尚无文件时，可建议 upload_materials。
- 投资/立项沟通为主时 suggested_origin_mode=research_programming。
- completeness_score / evidence_ratio / assumption_ratio 仅兼容字段；以 dimensions 为准。
- 另输出 reasons（3–5 条）：每条含 factor、evidence、impact、confidence、
  polarity（support|block|nuance）、related_axis（facts|intent|constraints|…）。
  让建筑师看懂「为何推荐这条路径」，不要黑盒。例如寺庙案例：意图清晰(support) +
  基地资料不足(block) → 因此 explore，而非先逼上传。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_context_assessment_user_prompt(
    *,
    user_text: str,
    project_name: str = "",
    document_count: int = 0,
    document_summaries: str = "",
    fact_lines: str = "",
    knowledge_lines: str = "",
    chunk_excerpts: str = "",
    gap_lines: str = "",
    confirmed_fact_count: int = 0,
    pending_fact_count: int = 0,
    knowledge_item_count: int = 0,
    blocking_gap_count: int = 0,
) -> str:
    return f"""请评估以下项目输入的知识状态（多维），并给出 2–4 条下一步建议。

项目名称：{project_name or "（未命名）"}
用户描述：
{user_text.strip()}

已上传资料数量：{document_count}
资料文件：
{document_summaries.strip() or "（暂无）"}

已确认事实数：{confirmed_fact_count}；待确认/提取事实数：{pending_fact_count}
【已提取/已确认事实】
{fact_lines.strip() or "（暂无）"}

项目知识条目数：{knowledge_item_count}
【项目知识条目】（研究写回 / 已确认陈述，含出处标记）
{knowledge_lines.strip() or "（暂无）"}

【资料摘录】
{chunk_excerpts.strip() or "（暂无）"}

阻断缺口数：{blocking_gap_count}
【知识缺口】
{gap_lines.strip() or "（暂无）"}

请输出 dimensions（六维）、completeness_score（兼容聚合）、maturity_stage、
evidence_ratio、assumption_ratio、known、unknown、missing_information、
suggested_origin_mode、understanding_summary、actions、reasons（3–5 条判断依据）。
known 尽量引用上述事实、知识条目或摘录；missing_information 优先覆盖知识缺口。
理解摘要中请点出「意图 vs 资料」是否分离（例如意图清/资料少）。
reasons 须能解释「为何是这条下一步」，勿空泛复述 summary。
"""
