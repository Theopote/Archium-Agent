"""Prompts for ArtDirection generation."""

from __future__ import annotations

from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.visual.preferences import VisualPreferences
from archium.prompts.identity import ARCHIUM_IDENTITY

ART_DIRECTION_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：你是一名建筑汇报视觉总监。
你的任务不是设计单页坐标，也不是套用固定模板。
你需要根据项目任务、成果目的、受众、叙事结构和素材性质，定义整套成果的视觉语言。

必须输出合法 JSON，字段包括：
- concept_name
- rationale
- visual_tone
- emotional_keywords
- palette_strategy
- typography_strategy
- grid_strategy
- image_strategy
- drawing_strategy
- diagram_strategy
- annotation_strategy
- cover_strategy
- section_strategy
- content_strategy
- closing_strategy
- pacing_strategy
- consistency_rules
- forbidden_styles

不得输出：
- 页面坐标
- 任意字体文件路径
- 未经用户确认的品牌规范
- 过度抽象的“高级、简约、科技感”而无解释
- 与项目不相关的装饰风格

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。
- 不要按医院/寺庙/乡村等项目类型直接套固定页面结构。
"""


def build_art_direction_user_prompt(
    *,
    brief: PresentationBrief | None,
    storyline: Storyline | None,
    preferences: VisualPreferences,
    deliverable_id: str | None = None,
    mission_id: str | None = None,
) -> str:
    brief_text = brief.model_dump_json() if brief is not None else "（无 Brief）"
    storyline_text = storyline.model_dump_json() if storyline is not None else "（无 Storyline）"
    return (
        "请为以下建筑汇报成果生成 ArtDirection JSON。\n\n"
        f"【deliverable_id】{deliverable_id or 'n/a'}\n"
        f"【mission_id】{mission_id or 'n/a'}\n"
        f"【用户视觉偏好】\n{preferences.model_dump_json()}\n\n"
        f"【PresentationBrief】\n{brief_text}\n\n"
        f"【Storyline】\n{storyline_text}\n"
    )
