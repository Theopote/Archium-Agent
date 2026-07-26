"""Architectural Reasoning Framework — shared process for building prompts.

Version history
---------------
v1 (2026-07-25): Initial five-step chain + quality criteria.
  Purpose: stop task-only prompts that skip problem → spatial translation.
v1.1 (2026-07-26): Clarify Step outputs land in design_rationale chain when schema supports it.
"""

from __future__ import annotations

ARCHITECTURAL_REASONING_VERSION = "architectural_reasoning.v1"

ARCHITECTURAL_REASONING_FRAMEWORK = """\
【建筑推理框架 Architectural Reasoning — 必须遵守】
不要直接「生成一个漂亮方案」。按下列步骤推理；结构化输出中的 design_rationale
（observation → interpretation → problem → hypothesis → strategy）应能追溯到这些步骤。

Step 1 · Context Understanding（语境）
- 地点 / 时间 / 社会背景 / 使用者 / 文化语境（已知写已知，未知标未知）。
- 禁止假装已有任务书、面积或现场证据。
- → 写入 design_rationale.observation（及可选 interpretation）。

Step 2 · Problem Identification（问题）
- 不问「要设计什么建筑」，而问「为什么需要它？它回应什么矛盾或缺位？」
- 错误示例：建设一个图书馆。
- 正确示例：解决年轻人缺少公共交流与学习停留空间的问题。
- → 写入 design_rationale.problem。

Step 3 · Design Intent（意图）
- 核心理念、价值目标、体验目标；可写成可讨论的主张，而非风格标签。
- → 写入 design_rationale.hypothesis / statement。

Step 4 · Spatial Translation（空间转译）
- 抽象概念必须落到空间组织：轴线、院落、嵌入、线性、层级、路径、采光、景观渗透等。
- 「人与自然共生」不可停在口号；须写出对应空间策略。
- → 写入 design_rationale.strategy（方向卡片 spatial_strategy 为表达层细化）。

Step 5 · Architectural Expression（表达）
- 体量、轮廓、材料与构造气质、氛围——服务于前述问题与空间策略，而非先行。

Step 6 · Verification（验证）
- 列出风险、未验证假设、缺证；考虑至少一条可替换路径（可在 rationale / risks 中体现）。
- → 写入 design_rationale.risks / evidence / alternatives。

【质量标准 Quality Criteria】
- 每个方向/结论必须能回答：回应了什么问题？空间如何承载？形式为何不是空转？
- 差异点清晰；禁止只换标题的同质方案。
- 不得编造精确指标；缺证据时写入未知/风险，不要用修辞填空。
"""
