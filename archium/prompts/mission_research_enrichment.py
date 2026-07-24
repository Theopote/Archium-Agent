"""Prompts for mission enrichment from confirmed public research."""

from __future__ import annotations

from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.prompts.project_mission import MISSION_SYSTEM_PROMPT

MISSION_RESEARCH_ENRICHMENT_SYSTEM_PROMPT = MISSION_SYSTEM_PROMPT + """\
本轮任务：将用户已确认的公开研究摘要整合进 ProjectMission 的 project_context（必要时更新 current_situation / key_unknowns）。

原则：
- 只整合【已确认公开研究】中的内容，不得编造新事实、数字或规范条文。
- project_context 应保留原有有效信息，并清晰加入研究结论与来源线索。
- 不得删除 task_statement 级别的核心任务定义（本步只返回 project_context 等补充字段）。
- 研究摘要仍是公开背景，不得写成已核实的项目事实；用语保持「公开资料表明…」「案例显示…」等克制表述。
- key_unknowns 仅补充仍待项目确认的问题；不要把已写明的研究结论重复列为未知。
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
    )
