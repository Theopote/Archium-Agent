"""Prompts for mission enrichment from confirmed public research."""

from __future__ import annotations

from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.prompts.project_mission import MISSION_SYSTEM_PROMPT

MISSION_RESEARCH_ENRICHMENT_SYSTEM_PROMPT = MISSION_SYSTEM_PROMPT + """\
本轮任务：将用户已确认的公开研究摘要整合进 ProjectMission 的稳定任务语境
（project_context / 必要时 current_situation）。

原则：
- 只整合【已确认公开研究】中的内容，不得编造新事实、数字或规范条文。
- project_context 应保留原有有效信息，并清晰加入研究结论与来源线索。
- 不得删除 task_statement 级别的核心任务定义（本步只返回 project_context 等补充字段）。
- 研究摘要仍是公开背景，不得写成已核实的项目事实；用语保持「公开资料表明…」「案例显示…」等克制表述。
- 不要输出或改写 key_unknowns / confidence：实时认知由 KnowledgeState 维护。
"""


def format_confirmed_research_block(items: list[ProjectKnowledgeItem]) -> str:
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        summary = item.statement.strip().split("\n\n")[0]
        lines.append(f"{index}. {summary}")
        if item.source_citations:
            citation = item.source_citations[0]
            if citation.url:
                title = citation.source_title or citation.url
                lines.append(f"   来源：{title} ({citation.url})")
            elif citation.source_title:
                lines.append(f"   来源：{citation.source_title}")
    return "\n".join(lines)


def build_mission_research_enrichment_prompt(
    *,
    current_mission_json: str,
    confirmed_research_block: str,
) -> str:
    return (
        "请根据已确认公开研究，生成 MissionResearchEnrichmentDraft JSON。\n\n"
        f"【当前任务理解】\n{current_mission_json}\n\n"
        f"【已确认公开研究】\n{confirmed_research_block or '（无）'}\n\n"
        "返回更新后的 project_context（完整文本，不是增量片段）。"
        "如 current_situation 需要补充公开背景，可一并更新；否则返回 null。"
        "不要修改 key_unknowns。"
    )


MISSION_RESEARCH_REVISION_SYSTEM_PROMPT = MISSION_SYSTEM_PROMPT + """\
本轮任务：在公开研究已写入 project_context 后，轻量修订 ProjectMission 的稳定任务定义
（task_statement / research_questions）。

原则：
- 仅基于【当前任务理解】与【已写回公开研究】做措辞级修订，不得编造面积、造价、规范或用地指标。
- task_statement 保持原任务性质，可补充「基于公开案例/背景」等研究语境，但不要改成完全不同的任务。
- research_questions 可调整仍待项目确认的研究问句；不要改写 key_unknowns / confidence。
- 实时认知缺口由 KnowledgeState 维护，本步只更新稳定任务定义。
- 不得把公开研究结论写成已核实项目事实。
"""


def build_mission_research_revision_prompt(
    *,
    current_mission_json: str,
    written_research_block: str,
) -> str:
    return (
        "请根据已写回公开研究，生成 MissionResearchRevisionDraft JSON。\n\n"
        f"【当前任务理解】\n{current_mission_json}\n\n"
        f"【已写回公开研究】\n{written_research_block or '（无）'}\n\n"
        "可更新 task_statement、research_questions；不要输出 key_unknowns。"
    )
