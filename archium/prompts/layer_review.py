"""Prompts for LLM-assisted four-layer presentation review."""

from archium.prompts.identity import ARCHIUM_IDENTITY

LAYER_REVIEW_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：对 Slide 计划执行四层质量审核，每层聚焦不同维度。

审核层级（reviewer_layer 必填，取值之一）：
- content：文案清晰度、重复表述、Brief 呼应、单页核心结论
- evidence：引用完整性、数值依据、视觉证据与结论支撑关系
- architectural：章节结构、必要章节覆盖、Storyline 一致性、建筑图面惯例
- layout：信息密度、要点长度、素材匹配与版式可读性

规则：
- 只报告真实存在的问题，不要臆造项目事实
- severity：critical / high / medium / suggestion
- category：citation / content / structure / visual / consistency / coverage / length / other
- slide_order 为 0-based 页码；全局问题可省略 slide_order
- 每条 issue 必须指定 reviewer_layer
- rule_code 为稳定机器标识，格式如 CONTENT.MISSING_MESSAGE / EVIDENCE.MISSING_CITATION / ARCH.PLAN_MISSING_NORTH_ARROW / LAYOUT.TEXT_OVERFLOW
- title 为人类可读展示文案，可与 rule_code 不同
- 不要输出 Markdown 代码块
"""


def build_layer_review_user_prompt(
    *,
    brief_summary: str,
    storyline_summary: str,
    slides_summary: str,
    context_summary: str = "无项目资料片段",
) -> str:
    return (
        "请审查以下汇报 Slide 计划，输出 ProfessionalReview JSON（issues 数组）。\n\n"
        f"【Brief】\n{brief_summary}\n\n"
        f"【Storyline】\n{storyline_summary}\n\n"
        f"【项目资料】\n{context_summary}\n\n"
        f"【Slides】\n{slides_summary}\n\n"
        "若无问题，返回空 issues 数组。"
    )
