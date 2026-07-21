"""Prompts for outline planning between Storyline and SlideSpec."""

from archium.prompts.identity import ARCHIUM_IDENTITY

OUTLINE_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为 Outline Planner，在 Storyline 章节与 SlideSpec 页面之间生成可编辑的汇报大纲。

专业原则：
- 大纲章节应比 Storyline 更贴近最终页级结构，但仍不是完整 SlideSpec。
- 必须承接 Storyline.narrative_arc：每一章标注 narrative_position，说明如何推进论证。
- 每个章节必须只有一个 key_message（该章节要传达的核心结论）。
- advances_from_previous 说明相对上一章推进了什么；prepares_for_next 说明为下一章铺垫什么。
- 禁止只增加信息而不推进叙事；禁止章节之间突然跳跃。
- estimated_slide_count 表示预计页数，总和应接近 target_slide_count。
- 不得编造项目事实；证据不足时在 evidence_requirements 中列出需要补充的资料。
- 参考案例、公开资料不得写成当前项目事实。

输出必须是合法 JSON：
{
  "title": "汇报标题",
  "thesis": "总体论点",
  "audience": "汇报对象",
  "purpose": "汇报目的",
  "target_slide_count": 25,
  "audience_mode": "government",
  "sections": [
    {
      "id": "history",
      "title": "历史沿革",
      "purpose": "建立历史认知",
      "key_message": "村庄形成与演变脉络",
      "estimated_slide_count": 1,
      "evidence_requirements": ["历史资料", "老照片"],
      "required_assets": ["历史照片"],
      "required": true,
      "expanded": true,
      "order": 0,
      "category": "heritage",
      "narrative_position": {
        "stage": "context",
        "advances_from_previous": "从封面进入历史语境",
        "prepares_for_next": "为价值判断与问题诊断提供背景"
      }
    }
  ]
}

narrative_position.stage 只能是：context / problem / evidence / tension / strategy / resolution / decision。
"""


def build_outline_plan_user_prompt(
    *,
    project_context: str,
    brief_json: str,
    storyline_json: str,
    target_slide_count: int,
    audience_mode: str,
    template_hint: str | None = None,
    narrative_json: str | None = None,
    issue_map_json: str | None = None,
) -> str:
    template_block = ""
    if template_hint:
        template_block = f"\n【建议章节结构参考】\n{template_hint}\n"
    narrative_block = ""
    if narrative_json:
        narrative_block = f"\n【文化叙事计划】\n{narrative_json}\n"
    issue_map_block = ""
    if issue_map_json:
        issue_map_block = f"\n【改造问题图】\n{issue_map_json}\n"
    return (
        f"请生成约 {target_slide_count} 页对应的 OutlinePlan JSON。\n"
        f"受众模式：{audience_mode}\n"
        "每个 section 必须包含 narrative_position，并与 Storyline.narrative_arc 对齐。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        f"【Storyline】\n{storyline_json}\n"
        f"{template_block}"
        f"{narrative_block}"
        f"{issue_map_block}\n"
        "章节 category 建议使用：intro/context/heritage/culture/problem/strategy/"
        "technical/implementation/decision/general。"
    )
