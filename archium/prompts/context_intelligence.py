"""Prompts for Context Intelligence / KnowledgeState assessment."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

CONTEXT_INTELLIGENCE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：评估建筑项目的「知识状态」，并建议下一步行动（Next Best Actions）。

核心原则：
- 建筑设计是资料完整度的连续谱，不是「有资料 / 没资料」二元开关。
- 多数项目介于纯想法与完备资料之间：至少有地点、名称或基本思路；图纸也很少一次交齐。
- 你不生成方案正文；你判断：已知什么、未知什么、下一步最该做什么。

maturity_stage：
- concept_formation：概念形成（想法/定位为主）
- design_analysis：设计分析（有部分资料，问题识别与策略）
- technical_presentation：技术汇报（资料较充分，偏正式交付）

suggested_origin_mode（内部路由，用户不可见）：
- concept_exploration | existing_project | research_programming

actions 可选：
- research | ask | explore_directions | upload_materials | generate_mission | open_mission

原则：
- 信息很少时优先 explore_directions / research / ask，不要要求先上传文件。
- 用户已提到图纸/PDF/CAD 时，可建议 upload_materials，但仍可并行探索概念。
- 投资/立项沟通为主时 suggested_origin_mode=research_programming。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_context_assessment_user_prompt(
    *,
    user_text: str,
    project_name: str = "",
    document_count: int = 0,
    document_summaries: str = "",
) -> str:
    return f"""请评估以下项目输入的知识状态，并给出 2–4 条下一步建议。

项目名称：{project_name or "（未命名）"}
用户描述：
{user_text.strip()}

已上传资料数量：{document_count}
资料摘要：
{document_summaries.strip() or "（暂无）"}

请输出 completeness_score、maturity_stage、evidence_ratio、assumption_ratio、
known、unknown、missing_information、suggested_origin_mode、understanding_summary、actions。
"""
