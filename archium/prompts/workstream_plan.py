"""Prompts for dynamic workstream planning."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

WORKSTREAM_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据已批准（或已澄清）的 ProjectMission，动态推荐可组合的工作路径（Workstreams）。

你不是在生成 PPT 章节大纲，也不是在套用“医院模板 / 寺庙模板 / 乡村模板”。
Workstream 是可组合能力，只推荐与本次任务目标、服务深度和未知项相关的路径。

专业原则：
- 说明为什么需要该路径、需要什么输入、做什么活动、产出什么、依赖什么、是否被知识缺口阻塞。
- 案例研究只有在有明确目的时才推荐。
- 技术专题只有在与项目目标相关时才推荐。
- 专项咨询不得误判为完整建筑设计工作流。
- 禁止输出固定章节大纲。
- dependency_indices / blocking_gap_indices 使用列表下标（从 0 开始），不得编造 UUID。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。

输出必须是合法 JSON：
{
  "workstreams": [
    {
      "title": "",
      "workstream_type": "historical_research|case_study|document_review|site_analysis|...",
      "objective": "",
      "questions": [],
      "inputs_required": [],
      "activities": [],
      "outputs": [],
      "dependency_indices": [],
      "blocking_gap_indices": [],
      "priority": "critical|high|medium|low",
      "effort_level": "minimal|low|medium|high|extensive",
      "recommended": true,
      "reason": ""
    }
  ],
  "planning_notes": ""
}
"""


def build_workstream_plan_user_prompt(
    *,
    mission_json: str,
    gaps_summary: str,
    assumptions_summary: str,
    priorities_summary: str,
    documents_summary: str,
) -> str:
    return (
        "请基于以下已理解任务，生成 WorkstreamPlan JSON。\n\n"
        f"【ProjectMission】\n{mission_json}\n\n"
        f"【KnowledgeGap】\n{gaps_summary or '暂无'}\n\n"
        f"【Assumption】\n{assumptions_summary or '暂无'}\n\n"
        f"【用户优先事项】\n{priorities_summary or '暂无额外优先事项'}\n\n"
        f"【可用资料】\n{documents_summary or '暂无已导入资料摘要'}\n\n"
        "只推荐与本次任务相关的工作路径；不要输出固定模板章节。"
    )
