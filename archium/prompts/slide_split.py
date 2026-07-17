"""Prompts for LLM-assisted narrative slide splitting."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

SLIDE_SPLIT_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为内容过载的单页 SlideSpec 规划叙事合理的拆页方案（SlideSplitPlan）。

专业原则：
- 拆页目标是恢复叙事结构，不是简单按要点数量切半。
- 优先按语义边界拆分，例如「问题与原因」和「策略与措施」应分为两页。
- 每一页必须有独立的核心信息（message），能单独传达一个结论。
- 结论与证据不可分离：含数字/引用的要点应与对应 source_citations 同页。
- 视觉素材应跟随其支撑的要点，通过 visual_indices 指定归属。
- 不得删除、改写或新增要点原文；只能将现有 key_points 分配到 source 或 continuation。
- 每页 key_points 不超过 5 条。

拆分策略：
1. 识别页面内的叙事块（现状/问题、原因、策略、决策等）。
2. 在叙事块边界处拆分，使每页主题单一。
3. 为每页撰写独立 title 与 message，保留章节上下文。
4. 按要点内容为每页分配 citation_indices 与 visual_indices（0-based，来自原文列表）。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要编造项目数据或新要点。
- 不要使用「本页延续上一页内容」类占位 message。
- 不要遗漏任何原页要点。

输出必须是合法 JSON，字段包括：
narrative_reason, source{title,message,key_points,citation_indices,visual_indices},
continuation{title,message,key_points,citation_indices,visual_indices}
"""


def build_slide_split_user_prompt(
    *,
    slide_summary: str,
    split_trigger: str,
    key_points_numbered: str,
    citations_numbered: str,
    visuals_numbered: str,
    chapter_summary: str,
    brief_summary: str,
) -> str:
    return (
        "请为以下过载页面规划叙事合理的两页拆分方案。\n\n"
        f"【拆页触发原因】\n{split_trigger}\n\n"
        f"【Brief 摘要】\n{brief_summary}\n\n"
        f"【章节上下文】\n{chapter_summary}\n\n"
        f"【当前页面】\n{slide_summary}\n\n"
        f"【要点列表（必须全部分配，不可改写）】\n{key_points_numbered}\n\n"
        f"【引用列表（citation_indices 引用此编号）】\n{citations_numbered or '（无）'}\n\n"
        f"【视觉素材（visual_indices 引用此编号）】\n{visuals_numbered or '（无）'}\n"
    )
