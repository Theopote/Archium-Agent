"""Prompts for LLM-assisted professional presentation review."""

from archium.prompts.identity import ARCHIUM_IDENTITY

PROFESSIONAL_REVIEW_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：作为建筑汇报专业审核专家，审查 Slide 计划的专业性、逻辑与表达质量。

审核维度：
- 结构：章节是否完整、叙事是否连贯
- 内容：每页是否只有一个核心结论、表述是否专业
- 一致性：与 Brief/Storyline 是否一致
- 覆盖度：是否遗漏关键决策点或必要章节

输出要求：
- 只报告真实存在的问题，不要臆造项目事实。
- severity 取值：critical / high / medium / suggestion
- category 取值：citation / content / structure / visual / consistency / coverage / length / other
- slide_order 为 0-based 页码；全局问题可省略 slide_order
- 不要输出 Markdown 代码块
"""


def build_professional_review_user_prompt(
    *,
    brief_summary: str,
    storyline_summary: str,
    slides_summary: str,
) -> str:
    return (
        "请审查以下汇报 Slide 计划，输出 ProfessionalReview JSON（issues 数组）。\n\n"
        f"【Brief】\n{brief_summary}\n\n"
        f"【Storyline】\n{storyline_summary}\n\n"
        f"【Slides】\n{slides_summary}\n\n"
        "若无问题，返回空 issues 数组。"
    )
