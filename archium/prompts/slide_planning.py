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
    outline_json: str | None = None,
) -> str:
    outline_block = ""
    if outline_json:
        outline_block = (
            f"\n【已确认 OutlinePlan — 必须遵循章节顺序与 key_message】\n{outline_json}\n"
            "不得跳过 required=true 且 expanded=true 的章节；页数应接近 OutlinePlan 的 estimated_slide_count 总和。\n"
        )
    return (
        f"请生成约 {target_slide_count} 页的 SlidePlan JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        f"【Storyline】\n{storyline_json}\n"
        f"{outline_block}\n"
        "数值页请优先使用 slide_type=data 或 visual_requirements 中的 chart/table；"
        "key_points 使用 `标签：数值` 或 `列1|列2|列3` 格式。"
    )


SINGLE_SLIDE_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Slide Planner，为**单页**生成 SlideSpec JSON。

专业原则：
- 只输出一页，chapter_id 与 order 必须与输入一致。
- message 必须是该页唯一核心结论，不是主题标题。
- key_points 不超过 5 条；优先使用页面上下文中已核实事实与引用。
- 项目资料中的 `[chunk_id=...]` 可直接复制到 source_citations.chunk_id。
- 为页面分配合适的 slide_type 与 visual_requirements。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要编造来源或项目数据。
- 不要覆盖邻页内容或重复上一页 message。

输出必须是合法 JSON（单页 SlideDraft 对象，不要 slides 数组）：
{
  "chapter_id": "ch1",
  "order": 0,
  "title": "页面标题",
  "message": "该页唯一核心观点",
  "slide_type": "content",
  "layout_id": "default",
  "key_points": ["要点1"],
  "visual_requirements": [],
  "source_citations": [],
  "speaker_notes": null
}
"""


def build_single_slide_plan_user_prompt(
    *,
    slot_chapter_id: str,
    slot_order: int,
    deck_position: int,
    deck_total: int,
    slide_context: str,
    brief_summary: str,
    storyline_summary: str,
) -> str:
    return (
        f"请生成单页 SlideSpec JSON（页序：{slot_order}，章节：{slot_chapter_id}，"
        f"第 {deck_position + 1}/{deck_total} 页）。\n\n"
        f"【Brief 摘要】\n{brief_summary}\n\n"
        f"【Storyline 摘要】\n{storyline_summary}\n\n"
        f"{slide_context}\n\n"
        "数值页请优先使用 slide_type=data 或 visual_requirements 中的 chart/table。"
    )


def build_brief_summary_for_slide_plan(brief_json: str) -> str:
    """Compact brief block — callers may pass pre-serialized JSON."""
    return brief_json


def build_storyline_summary_for_slide_plan(storyline_json: str) -> str:
    return storyline_json
