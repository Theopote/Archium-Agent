"""Prompts for entry intent / orientation classification."""

from __future__ import annotations

from archium.prompts.identity import ARCHIUM_IDENTITY

ENTRY_INTENT_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据用户的一段自由描述，判断进入 Archium 的「主路径取向」。

重要产品事实：
- 建筑设计项目很少「零资料」或「资料完备」。常见是部分资料 + 地址/名称/基本思路。
- 取向不是互斥完备态：只表示先走哪条主路径，之后仍可交叉补充。

三种取向（orientation）：
1. concept_exploration — 以想法/概念为主；即使只有地点、名称、一句话思路也适用。
2. existing_project — 以现有图纸/PDF/照片等资料整理汇报为主；资料可不完整。
3. research_programming — 以策划、可研、投资人沟通、决策未知项梳理为主。

原则：
- 不要因为「提到了地点」就默认 existing；没有明确要整理已有资料时优先 concept。
- 用户强调上传/改造汇报/已有图纸 → existing_project。
- 用户强调投资逻辑、功能定位、立项沟通 → research_programming。
- confidence 为 0–1；信息混杂时给较低分。
- 输出合法 JSON，字段与 schema 一致。
"""


def build_entry_intent_user_prompt(*, user_text: str) -> str:
    return f"""请判断以下描述的主路径取向。

用户描述：
{user_text.strip()}

请输出：
- orientation: concept_exploration | existing_project | research_programming
- confidence: 0–1
- rationale: 一句中文理由（承认资料可不完整）
- suggested_next: 一句建议下一步（例如进入概念探索 / 上传资料 / 进入策划任务）
"""
