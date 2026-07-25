"""Research → design knowledge extraction (not case dump).

Version history
---------------
v1 (2026-07-25): Require transferable principles over case lists.
"""

from __future__ import annotations

RESEARCH_KNOWLEDGE_FRAMEWORK_VERSION = "research_knowledge.v1"

RESEARCH_KNOWLEDGE_FRAMEWORK = """\
【研究知识提炼 Research → Design Knowledge — 必须遵守】
不要罗列案例清单。要把检索片段提炼为可讨论的设计知识。

每个 finding 的 key_points 应尽量覆盖（检索不足则写明未覆盖）：
1. 可迁移设计原则（principle）
2. 空间组织方式（spatial organization）
3. 材料 / 构造策略（material / tectonic）
4. 与当前项目的关联（project link）——可与 relevance 呼应
5. 适用边界 / 是否适用（applicability）——气候、尺度、制度、文化差异

原则：
- 优先依据【联网检索结果】；不得编造检索未出现的事实与规范条文。
- 不确定时降低表述强度，写「检索片段未覆盖」。
- suggested_sources 只能引用检索结果中的 URL。
"""
