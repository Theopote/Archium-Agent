"""Prompts for Vision Engine visual concept briefs (text-first)."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

VISUAL_CONCEPT_BRIEF_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为已选定或草稿中的建筑概念方向，撰写一份视觉概念简报（Visual Concept Brief）。

你不是在做正式施工图或现场勘测照片。
目标是给出可交给 Vision Engine Prompt Compiler 的示意性视觉意图：构图、氛围、图示意图。

专业原则：
- 视觉必须回应该概念方向的主题、空间想法与差异点，避免套通用地产渲染话术。
- image_type 仅可从：concept_sketch, atmosphere_image, site_diagram, sketch_note。
- style_preset 仅可从：competition_concept_sketch, marker_sketch, soft_sketch,
  soft_atmosphere, watercolor_note, flat_analytical_diagram。
- subject / elements 写可绘制的建筑语义；avoid 写禁止的商业渲染套路。
- 不得编造面积、容积率等精确指标。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_visual_concept_brief_user_prompt(
    *,
    mission_title: str,
    task_statement: str,
    direction_title: str,
    direction_summary: str,
    theme: str,
    spatial_idea: str,
    experience_focus: str,
    differentiator: str,
) -> str:
    return f"""请为以下概念方向撰写一份视觉概念简报。

任务标题：{mission_title}
任务陈述：{task_statement}

概念方向标题：{direction_title}
方向摘要：{direction_summary}
主题：{theme or "（暂无）"}
空间想法：{spatial_idea or "（暂无）"}
体验焦点：{experience_focus or "（暂无）"}
差异点：{differentiator or "（暂无）"}

要求：
1. 输出 title, composition_intent, atmosphere, diagram_intent,
   image_type, style_preset, subject, elements, avoid。
2. composition_intent 说明主构图与视线；atmosphere 说明光、材质与情绪。
3. 默认偏概念草图或软氛围示意，除非方向明确需要图示分析。
"""
