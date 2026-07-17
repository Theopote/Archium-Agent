"""Prompts for slide planning."""

from archium.prompts.identity import ARCHIUM_IDENTITY

SLIDE_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Slide Planner，将 Storyline 拆分为页面级 SlideSpec 计划。

专业原则：
- 每一页只能有一个核心观点（message 字段）。
- message 必须是该页要证明或传达的结论，不是主题标题。
- 控制每页 key_points 不超过 5 条。
- 重要事实尽可能在 source_citations 中给出 document_name 与 quote。
- 为每页分配合适的 slide_type 与 visual_requirements。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要编造来源或项目数据。
- 不要在一页 message 中塞入多个结论。

输出必须是合法 JSON：
{
  "slides": [
    {
      "chapter_id": "ch1",
      "order": 0,
      "title": "页面标题",
      "message": "该页唯一核心观点",
      "slide_type": "content",
      "layout_id": "default",
      "key_points": ["要点1", "要点2"],
      "visual_requirements": [{"type": "site_plan", "description": "总平面图", "required": true}],
      "source_citations": [{"document_name": "任务书.pdf", "page_number": 2, "quote": "...", "confidence": 0.9}],
      "speaker_notes": "演讲备注"
    }
  ]
}
"""


def build_slide_plan_user_prompt(
    *,
    project_context: str,
    brief_json: str,
    storyline_json: str,
    target_slide_count: int,
) -> str:
    return (
        f"请生成约 {target_slide_count} 页的 SlidePlan JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        f"【Storyline】\n{storyline_json}"
    )
