"""Prompts for autonomous research synthesis (Planning / Research role)."""

from __future__ import annotations

from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.prompts.identity import ARCHIUM_IDENTITY

AUTONOMOUS_RESEARCH_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Research 角色，针对建筑/规划概念探索中的待研究项，基于【联网检索结果】产出可进入项目知识库的公开研究摘要。

专业原则：
- 这是「研究线索与公开背景 synthesis」，不是已确认项目事实。
- 必须优先依据【联网检索结果】中的标题、摘要片段进行归纳；不得编造检索结果中未出现的事实、数字或规范条文。
- 若检索结果不足以支撑某结论，明确写「检索片段未覆盖」或降低表述强度，不得臆测。
- 每个 finding 必须说明与当前设计问题的关联（relevance）。
- suggested_sources 只能引用【联网检索结果】里已给出的 URL；title 必须与检索结果标题一致或为其简称。
- 不得把推测写成已核实事实。

输出必须是合法 JSON：
{
  "findings": [
    {
      "topic": "研究主题",
      "summary": "2-4 句背景摘要",
      "key_points": ["要点1", "要点2"],
      "suggested_sources": [{"title": "来源名称", "url": "https://...", "note": "可查章节或说明"}],
      "relevance": "对本项目的启示"
    }
  ]
}
"""


def format_web_search_block(results: list[WebSearchResult]) -> str:
    if not results:
        return "（未获取到联网检索结果；请基于设计语境做保守归纳，且 suggested_sources 留空 url。）"
    lines: list[str] = []
    for index, hit in enumerate(results, start=1):
        snippet = hit.snippet.strip() or "（无摘要片段）"
        lines.append(
            f"[{index}] {hit.title}\n"
            f"URL: {hit.url}\n"
            f"Snippet: {snippet}"
        )
    return "\n\n".join(lines)


def build_autonomous_research_user_prompt(
    *,
    project_name: str,
    design_context: str,
    research_topics: list[str],
    web_search_results: list[WebSearchResult] | None = None,
) -> str:
    topics_block = "\n".join(f"- {topic.strip()}" for topic in research_topics if topic.strip())
    search_block = format_web_search_block(web_search_results or [])
    return (
        f"请针对以下待研究项，生成 AutonomousResearchDraft JSON。\n\n"
        f"【项目名称】\n{project_name or '未命名项目'}\n\n"
        f"【设计使命 / 任务语境】\n{design_context.strip() or '暂无'}\n\n"
        f"【待研究项】\n{topics_block or '（无具体主题，请基于设计语境提出 2-3 项公开背景研究）'}\n\n"
        f"【联网检索结果】\n{search_block}\n\n"
        "每项 finding 对应一个待研究主题或子问题；全部标记为待用户确认，不得作为已确认事实。"
        "suggested_sources 中的 url 必须来自【联网检索结果】。"
    )
