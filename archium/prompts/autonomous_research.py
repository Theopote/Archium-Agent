"""Prompts for autonomous research synthesis (Planning / Research role).

PROMPT_VERSION history
----------------------
autonomous_research.v1 — search-grounded synthesis + citations
autonomous_research.v2 — Research → Design Knowledge framework
autonomous_research.v3 — structured DesignKnowledge fields on findings
"""

from __future__ import annotations

from archium.infrastructure.research.web_search.models import WebSearchResult
from archium.prompts.frameworks.research_knowledge import RESEARCH_KNOWLEDGE_FRAMEWORK
from archium.prompts.identity import ARCHIUM_IDENTITY

PROMPT_VERSION = "autonomous_research.v3"

AUTONOMOUS_RESEARCH_SYSTEM_PROMPT = (
    ARCHIUM_IDENTITY
    + """\
当前任务：作为 Research 角色，针对建筑/规划概念探索中的待研究项，基于【联网检索结果】产出可进入项目知识库的公开研究摘要。

这是「研究线索与公开背景 synthesis」，不是已确认项目事实。

"""
    + RESEARCH_KNOWLEDGE_FRAMEWORK
    + """
输出必须是合法 JSON（字段与 schema 一致）：
{
  "findings": [
    {
      "topic": "研究主题",
      "summary": "2-4 句背景摘要",
      "insight": "为何对设计重要（非案例罗列）",
      "principle": "可迁移设计原则",
      "spatial_translation": "空间组织启示（院落/轴线/嵌入等）",
      "material_strategy": "材料或构造倾向（可空）",
      "project_link": "与当前项目的关联",
      "applicability": "适用边界（气候/尺度/文化等）",
      "evidence": ["证据标签1"],
      "key_points": ["原则：…", "空间：…"],
      "suggested_sources": [{"title": "来源名称", "url": "https://...", "note": "说明"}],
      "relevance": "对本项目的设计启示"
    }
  ]
}

必须填写 insight、principle、spatial_translation、project_link（检索不足则写「检索片段未覆盖」）。
"""
)


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
        f"请按【研究知识提炼】针对以下待研究项，生成 AutonomousResearchDraft JSON。\n\n"
        f"【项目名称】\n{project_name or '未命名项目'}\n\n"
        f"【设计使命 / 任务语境】\n{design_context.strip() or '暂无'}\n\n"
        f"【待研究项】\n{topics_block or '（无具体主题，请基于设计语境提出 2-3 项公开背景研究）'}\n\n"
        f"【联网检索结果】\n{search_block}\n\n"
        "每项 finding 对应一个待研究主题或子问题；全部标记为待用户确认，不得作为已确认事实。"
        "优先填写 insight / principle / spatial_translation / project_link / applicability；"
        "key_points 可用「原则/空间/材料/关联/适用」标签补充。"
        "suggested_sources 中的 url 必须来自【联网检索结果】。"
    )
