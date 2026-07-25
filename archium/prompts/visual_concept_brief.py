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
    spatial_strategy: str = "",
    formal_language: str = "",
    material_strategy: str = "",
    reference_dna: str = "",
    visual_prompt_block: str = "",
    design_rationale_block: str = "",
) -> str:
    structured = ""
    if spatial_strategy.strip():
        structured += f"\n空间策略：{spatial_strategy.strip()}"
    if formal_language.strip():
        structured += f"\n形式语言：{formal_language.strip()}"
    if material_strategy.strip():
        structured += f"\n材料策略：{material_strategy.strip()}"
    if reference_dna.strip():
        structured += f"\n参照基因：{reference_dna.strip()}"
    if visual_prompt_block.strip():
        structured += f"\n{visual_prompt_block.strip()}"
    if design_rationale_block.strip():
        structured += f"\n设计推理：\n{design_rationale_block.strip()}"
    return f"""请为以下概念方向撰写一份视觉概念简报。

任务标题：{mission_title}
任务陈述：{task_statement}

概念方向标题：{direction_title}
方向摘要：{direction_summary}
主题：{theme or "（暂无）"}
空间想法：{spatial_idea or "（暂无）"}
体验焦点：{experience_focus or "（暂无）"}
差异点：{differentiator or "（暂无）"}{structured or chr(10) + "（暂无结构化空间/形式字段）"}

要求：
1. 输出 title, composition_intent, atmosphere, diagram_intent,
   image_type, style_preset, subject, elements, avoid。
2. composition_intent 说明主构图与视线；atmosphere 说明光、材质与情绪。
3. 默认偏概念草图或软氛围示意，除非方向明确需要图示分析。
"""


VISUAL_SEED_REFINE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据建筑师对概念示意的反馈，修订概念方向的视觉种子（visual_prompt）
以及必要时微调空间/形式描述。

你不是在重写整份方案，也不是在做正式施工图。
目标是把「看图后的口头反馈」落成可再次出图的结构化种子。

专业原则：
- 优先保留原方向主题与差异点；只改反馈点名的部分。
- image_prompt 写可绘制的建筑场景语义（可中英混合）。
- camera / style 用简短可执行描述（如 architectural axonometric、concept sketch）。
- 若反馈未涉及某字段，可沿用当前值或留空字符串表示不改。
- change_summary 用一句中文说明改了什么。
- 不得编造面积、容积率等精确指标。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_visual_seed_refine_user_prompt(
    *,
    feedback: str,
    direction_title: str,
    direction_summary: str,
    spatial_strategy: str,
    formal_language: str,
    material_strategy: str,
    experience_focus: str,
    visual_prompt_block: str,
    brief_title: str = "",
    composition_intent: str = "",
    atmosphere: str = "",
) -> str:
    brief_block = ""
    if brief_title.strip() or composition_intent.strip() or atmosphere.strip():
        brief_block = (
            f"\n最近视觉简报：{brief_title or '（无标题）'}"
            f"\n构图意图：{composition_intent or '（暂无）'}"
            f"\n氛围：{atmosphere or '（暂无）'}"
        )
    return f"""请根据建筑师反馈修订概念方向的视觉种子。

建筑师反馈：
{feedback.strip()}

概念方向标题：{direction_title}
方向摘要：{direction_summary or "（暂无）"}
空间策略：{spatial_strategy or "（暂无）"}
形式语言：{formal_language or "（暂无）"}
材料策略：{material_strategy or "（暂无）"}
体验焦点：{experience_focus or "（暂无）"}
当前视觉种子：
{visual_prompt_block.strip() or "（暂无）"}{brief_block}

要求：
1. 输出 image_prompt, camera, style, spatial_strategy, formal_language,
   material_strategy, experience_focus, change_summary。
2. 未提及的字段尽量沿用当前值；明确要求改的字段必须改。
3. change_summary 一句中文，便于写入意图演进时间线。
"""
