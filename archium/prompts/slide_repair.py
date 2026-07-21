"""Prompts for repairing individual slides from review feedback."""

from archium.prompts.identity import ARCHIUM_IDENTITY

SLIDE_REPAIR_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据审核反馈，修订单页 SlideSpec 的标题、核心信息与要点。

专业原则：
- 保留原页叙事意图，只修复审核指出的问题。
- 核心信息保持一句完整结论，不要写成段落。
- 要点不超过 5 条，每条简洁有力。
- 不编造项目数据；缺失信息用「待确认」表述。

修复策略（由低到高）：
1. 缩短重复表达，不删除事实。
2. 改写句子，压缩冗余修饰。
3. 若仍超出版面，建议拆分为两页（不要直接删除要点）。
4. 若涉及数字、单位、项目名称、决策要求或风险条件，不得删除或省略，应保留并提示需人工确认。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。
- 不要通过删除最后一个要点来解决密度问题。
- 不要删除含数字、单位、决策或风险表述的要点。

输出必须是合法 JSON，字段包括：title, message, key_points
"""


def build_slide_repair_user_prompt(
    *,
    slide_summary: str,
    issue_summary: str,
    brief_summary: str,
    slide_context: str | None = None,
) -> str:
    context_block = ""
    if slide_context:
        context_block = f"\n【页面上下文（仅限本页）】\n{slide_context}\n"
    return (
        "请根据审核反馈修订以下页面 JSON。\n\n"
        f"【Brief 摘要】\n{brief_summary}\n"
        f"{context_block}\n"
        f"【当前页面】\n{slide_summary}\n\n"
        f"【待修复问题】\n{issue_summary}\n"
    )
