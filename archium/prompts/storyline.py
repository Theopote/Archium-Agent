"""Prompts for storyline generation."""

from archium.prompts.identity import ARCHIUM_IDENTITY

STORYLINE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Narrative Architect，根据 PresentationBrief 和项目上下文，建立章节化叙事结构。

专业原则：
- 章节之间必须有逻辑递进关系。
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
  "chapters": [
    {
      "id": "ch1",
      "title": "章节名",
      "purpose": "章节目的",
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
) -> str:
    narrative_block = ""
    if narrative_json:
        narrative_block = f"\n【文化叙事计划】\n{narrative_json}\n"
    return (
        "请根据 PresentationBrief 生成 Storyline JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}"
        f"{narrative_block}"
    )
