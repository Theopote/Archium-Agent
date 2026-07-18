"""Prompts for dynamic deliverable planning."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

DELIVERABLE_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据已理解的 ProjectMission、已选 Workstream 与决策需求，动态推荐成果（Deliverables）。

你不是在默认生成 20 页方案 PPT。
应根据用户目的、受众、工作路径、决策需求和项目阶段推荐：
- required：本轮必要成果
- optional：可选成果
- not_recommended：明确不建议的成果（说明原因）

专业原则：
- 每项成果必须说明服务的决策（decision_served）。
- 专项咨询不得默认推荐完整方案汇报 PPT。
- 概念汇报只有在用户目标包含汇报/决策沟通时才标为 required。
- Presentation 类成果可进入现有 Brief/Storyline 主链；其他成果本轮只需规划与保存。
- source_workstream_indices 使用工作路径列表下标（从 0 开始），不得编造 UUID。
- 禁止套用固定项目模板大纲。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。

输出必须是合法 JSON：
{
  "deliverables": [
    {
      "id": "del-xxx",
      "title": "",
      "deliverable_type": "presentation|report|case_study|question_list|...",
      "purpose": "",
      "audience": "",
      "content_scope": [],
      "source_workstream_indices": [],
      "recommendation": "required|optional|not_recommended",
      "format": "pptx|markdown|json",
      "expected_length": "",
      "notes": "",
      "decision_served": ""
    }
  ],
  "planning_notes": ""
}
"""


def build_deliverable_plan_user_prompt(
    *,
    mission_json: str,
    workstreams_summary: str,
    decisions_summary: str,
    audience_summary: str,
    stage_summary: str,
) -> str:
    return (
        "请基于以下信息生成 DeliverablePlan JSON。\n\n"
        f"【ProjectMission】\n{mission_json}\n\n"
        f"【已选/推荐 Workstream】\n{workstreams_summary or '暂无工作路径'}\n\n"
        f"【决策需求】\n{decisions_summary or '暂无'}\n\n"
        f"【受众与目的】\n{audience_summary or '暂无'}\n\n"
        f"【阶段与服务深度】\n{stage_summary or '暂无'}\n\n"
        "区分必要、可选与不建议成果；不要默认输出完整建筑设计 PPT。"
    )
