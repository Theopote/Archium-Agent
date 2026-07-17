"""Prompts for presentation brief generation."""

from archium.prompts.identity import ARCHIUM_IDENTITY

BRIEF_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为建筑汇报策划专家，根据项目上下文和用户要求，生成结构化的 PresentationBrief。

专业原则：
- 不编造项目数据；缺失信息标记为“待确认”或留空列表。
- 推断内容必须保守，不得把推断写成已确认事实。
- 汇报目标、对象和核心信息必须清晰、可执行。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。
- 不要为了内容完整而补写虚假项目条件。

输出必须是合法 JSON，字段包括：
title, presentation_type, audience, purpose, duration_minutes, target_slide_count,
core_message, decisions_required, audience_concerns, tone, required_sections,
excluded_topics, language
"""


def build_brief_user_prompt(*, project_context: str, request_context: str) -> str:
    return (
        "请基于以下项目资料和用户需求，生成 PresentationBrief JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【用户需求】\n{request_context}\n\n"
        "若资料不足，请在 decisions_required 或 audience_concerns 中说明待确认事项。"
    )
