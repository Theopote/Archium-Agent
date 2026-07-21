"""Prompts for storyline generation."""

from archium.prompts.identity import ARCHIUM_IDENTITY

STORYLINE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Narrative Architect，根据 PresentationBrief 和项目上下文，建立章节化叙事结构。

专业原则：
- 必须先确定整套演示的叙事弧线（narrative_arc），再规划 chapters。
- 叙事弧线遵循：建立背景/问题 → 构建复杂性或矛盾 → 给出解决方案 →（可选）明确决策请求。
- 每个章节必须推进该弧线，而不是并列堆叠话题；避免章节之间突然跳跃。
- 每个章节只有一个关键结论（key_message）。
- 不得直接生成最终 PPT 页面内容。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要编造项目数字或条件。
- 不要跳过 Brief 中的 required_sections。

输出必须是合法 JSON：
{
  "thesis": "总体论点",
  "narrative_pattern": "problem_solution",
  "narrative_arc": {
    "opening_context": "开场背景：听众需先理解的情境",
    "central_problem": "核心矛盾或必须回应的问题",
    "tension_building": ["加剧紧迫性的事实或冲突1", "冲突2"],
    "turning_point": "论证转折：从问题转向策略的关键判断",
    "proposed_resolution": "提出的解决路径",
    "final_decision": "结尾需要听众做出的决策或行动（可 null）"
  },
  "chapters": [
    {
      "id": "ch1",
      "title": "章节名",
      "purpose": "章节目的（说明如何推进叙事弧线）",
      "key_message": "章节关键结论",
      "order": 0,
      "estimated_slide_count": 4
    }
  ]
}
"""


def build_storyline_user_prompt(
    *,
    project_context: str,
    brief_json: str,
    narrative_json: str | None = None,
    issue_map_json: str | None = None,
) -> str:
    narrative_block = ""
    if narrative_json:
        narrative_block = f"\n【文化叙事计划】\n{narrative_json}\n"
    issue_map_block = ""
    if issue_map_json:
        issue_map_block = f"\n【改造问题图】\n{issue_map_json}\n"
    return (
        "请根据 PresentationBrief 生成 Storyline JSON。\n"
        "先填写 narrative_arc，再据此安排 chapters 顺序与 key_message。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}"
        f"{narrative_block}"
        f"{issue_map_block}"
    )
