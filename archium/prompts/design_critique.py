"""Prompts for Architectural Design Critic (concept challenge, not slide QA).

PROMPT_VERSION history
----------------------
design_critique.v1 — initial five questions inline
design_critique.v2 — shared DESIGN_CRITIQUE_FRAMEWORK include
"""

from __future__ import annotations

from archium.prompts.frameworks.design_critique import DESIGN_CRITIQUE_FRAMEWORK

PROMPT_VERSION = "design_critique.v2"

DESIGN_CRITIQUE_SYSTEM_PROMPT = (
    DESIGN_CRITIQUE_FRAMEWORK
    + """
输出约定：
- 只输出 DesignCritiqueDraft JSON。
- strengths / weaknesses / missing_evidence / alternative_directions 条目具体、可操作。
- challenge 取值：why | evidence | problem_fit | alternative | form_only
- severity：critical | high | medium | suggestion
- verdict：proceed | caution | reject
- alternative_directions 至少 1 条（可替换路径）。
"""
)


def build_design_critique_user_prompt(
    *,
    direction_block: str,
    design_intent_block: str,
    research_block: str,
) -> str:
    return (
        "请按【建筑批判框架】批判以下概念方向，输出 DesignCritiqueDraft JSON。\n\n"
        f"【概念方向】\n{direction_block.strip() or '（空）'}\n\n"
        f"【设计意图 / DesignIntent】\n{design_intent_block.strip() or '（空）'}\n\n"
        f"【研究与已知知识】\n{research_block.strip() or '（暂无研究摘要）'}\n"
    )
