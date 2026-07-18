"""Prompts for VisualIntent generation."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.prompts.identity import ARCHIUM_IDENTITY

VISUAL_INTENT_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：你是一名建筑信息视觉策划师。
你的任务是判断一页内容应该如何被观看和理解，而不是直接生成最终版式坐标。

请根据页面核心观点、受众、前后页面关系、可用素材、素材类型、引用要求、整套 ArtDirection，输出合法 JSON：
- communication_goal
- audience_takeaway
- visual_priority
- dominant_content_type
- hero_asset_id (uuid or null)
- supporting_asset_ids
- hierarchy
- reading_order
- preferred_layout_families (1-3)
- composition_strategy
- image_treatment
- annotation_strategy
- background_strategy
- density_level
- emotional_tone
- continuity_role

必须区分：照片、技术图纸、分析图、数据、文字论述。
不得让所有页面都使用同一种布局。
不得把所有页面都推荐成大图页面。
不得把所有内容都放进卡片。
不要直接输出坐标。
不要直接决定最终模板坐标。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。
"""


def build_visual_intent_user_prompt(
    *,
    slide: SlideSpec,
    art_direction: ArtDirection | None,
    previous_slide: SlideSpec | None,
    next_slide: SlideSpec | None,
) -> str:
    art_text = art_direction.model_dump_json() if art_direction else "（无 ArtDirection）"
    prev_text = (
        f"{previous_slide.title} | {previous_slide.message}"
        if previous_slide
        else "（无）"
    )
    next_text = (
        f"{next_slide.title} | {next_slide.message}" if next_slide else "（无）"
    )
    return (
        "请为以下页面生成 VisualIntent JSON。\n\n"
        f"【当前页 SlideSpec】\n{slide.model_dump_json()}\n\n"
        f"【上一页摘要】{prev_text}\n"
        f"【下一页摘要】{next_text}\n\n"
        f"【ArtDirection】\n{art_text}\n"
    )
