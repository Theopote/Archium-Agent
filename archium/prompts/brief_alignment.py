"""Prompts for LLM-assisted Brief-to-Slide semantic alignment."""

from archium.prompts.identity import ARCHIUM_IDENTITY

BRIEF_ALIGNMENT_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：判断 Slide 计划是否在语义层面呼应 Presentation Brief，而非仅做关键词匹配。

评估维度：
- 核心信息（core_message）是否在 Slide 结论中得到体现或推导
- 必要章节（required_sections）是否在叙事中有对应表达（允许同义表述）
- 需决策事项（decisions_required）是否在总结/行动页中有所回应

输出要求：
- 返回 BriefAlignment JSON
- aligned=true 表示语义上基本一致；false 表示存在明显遗漏或偏离
- gap_summary 用 1–2 句说明具体缺口（aligned=true 时可为空）
- confidence 取值 0.0–1.0
- 不要输出 Markdown 代码块
"""


def build_brief_alignment_user_prompt(
    *,
    brief_summary: str,
    slides_summary: str,
) -> str:
    return (
        "请评估 Slide 计划与 Brief 的语义对齐程度，输出 BriefAlignment JSON。\n\n"
        f"【Brief】\n{brief_summary}\n\n"
        f"【Slides】\n{slides_summary}\n"
    )
