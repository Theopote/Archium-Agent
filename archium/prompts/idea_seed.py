"""Prompts for IdeaSeed enrichment from a one-line idea.

PROMPT_VERSION history
----------------------
idea_seed.v1 — theme / inspiration / keywords
idea_seed.v2 — nudge toward problem clue (pre-reasoning), not just style tags
"""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

PROMPT_VERSION = "idea_seed.v2"

IDEA_SEED_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：把用户的一句话建筑想法解读为结构化 IdeaSeed。

这不是 ProjectMission，也不是方案定稿。
目标是提取可讨论的主题线索、灵感与关键词，供后续概念方向推演使用。

原则：
- 忠实于用户原话，不编造面积、投资、法规等精确指标。
- theme / inspiration 尽量点出「可能在回应什么问题或缺位」，避免只堆风格词。
- imagination_level 只能是 open / grounded / speculative 之一。
- keywords 3–6 个短词即可。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_idea_seed_user_prompt(*, raw_input: str, project_name: str = "") -> str:
    return f"""请解读以下一句话想法，输出结构化 IdeaSeed 字段。

项目名称：{project_name or "（未命名）"}
原始想法：
{raw_input}

请输出：
- theme：一句话主题线索（可含问题意识，不只是建筑类型）
- inspiration：灵感/追问方向（一句；可追问「为什么需要」）
- keywords：3–6 个关键词
- imagination_level：open | grounded | speculative
"""
