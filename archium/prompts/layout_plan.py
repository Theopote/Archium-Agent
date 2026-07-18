"""Prompts for layout family/variant decision (no coordinates)."""

from __future__ import annotations

from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.visual_intent import VisualIntent
from archium.prompts.identity import ARCHIUM_IDENTITY

LAYOUT_PLAN_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：你是建筑版式决策助手。
第一版你只负责：
- 从允许的 LayoutFamily 中选择
- 从允许的 variant 中选择
- 判断主次元素
- 判断内容是否需要拆页
- 判断密度是否过高

不允许自由输出全部坐标。几何位置由确定性 generator 生成。

输出合法 JSON：
- layout_family
- layout_variant
- hero_content_ref
- supporting_content_refs
- reading_order
- density_adjustment
- split_recommended
- split_reason

禁止事项：
- 不要输出 Markdown 代码块。
- 不要输出 x/y/width/height。
- 不要添加 schema 之外的字段。
"""


def build_layout_plan_user_prompt(
    *,
    slide: SlideSpec,
    intent: VisualIntent,
    art_direction: ArtDirection | None,
    allowed_families: list[str],
) -> str:
    art_text = art_direction.model_dump_json() if art_direction else "（无）"
    return (
        "请从允许的版式族中做出 LayoutDecisionDraft。\n\n"
        f"【允许的 LayoutFamily】{', '.join(allowed_families)}\n\n"
        f"【SlideSpec】\n{slide.model_dump_json()}\n\n"
        f"【VisualIntent】\n{intent.model_dump_json()}\n\n"
        f"【ArtDirection】\n{art_text}\n"
    )
