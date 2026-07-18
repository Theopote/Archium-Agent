"""Prompts for slide planning."""

from archium.prompts.identity import ARCHIUM_IDENTITY

SLIDE_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Slide Planner，将 Storyline 拆分为页面级 SlideSpec 计划。

专业原则：
- 每一页只能有一个核心观点（message 字段）。
- message 必须是该页要证明或传达的结论，不是主题标题。
- 控制每页 key_points 不超过 5 条。
- 项目资料中的 `[chunk_id=...]` 可直接复制到 source_citations.chunk_id。
- 为每页分配合适的 slide_type 与 visual_requirements。

数值与图表表达：
- 2 个及以上可对比数值（面积、床位数、比例等）→ 优先 `slide_type: "data"`，
  key_points 使用 `指标名：数值`（如 `总建筑面积：120000 ㎡`），系统会自动生成原生图表。
- 需要强调构成/占比 → 在 visual_requirements 中加入 `{"type": "chart", ...}`，
  或在标题/要点中出现「占比/比例/构成」字样以触发饼图。
- 多列对比（改造前/后、分期指标）→ visual_requirements 使用 `{"type": "table", ...}`，
  key_points 使用管道符表格行，如 `指标|改造前|改造后`、`建筑面积|80000|120000`。
- 单个 KPI → `slide_type: "data"`，1 条 key_point 即可。
- 优先引用【项目事实账本】中已确认数值，不要编造数据。

图纸与素材：
- 总图/平面图/剖面/效果图使用对应 visual_requirements（site_plan、floor_plan 等）。
- 不要在 key_points 或 message 中伪造指北针方向、比例尺或图例内容；
  这些由素材标注元数据负责，未标注时不应声称图纸已含这些元素。

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
      "source_citations": [{"document_name": "任务书.pdf", "chunk_id": "uuid", "page_number": 2, "quote": "...", "confidence": 0.9}],
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
        f"【Storyline】\n{storyline_json}\n\n"
        "数值页请优先使用 slide_type=data 或 visual_requirements 中的 chart/table；"
        "key_points 使用 `标签：数值` 或 `列1|列2|列3` 格式。"
    )
