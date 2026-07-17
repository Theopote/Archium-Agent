"""Prompts for repairing individual slides from review feedback."""

from archium.prompts.identity import ARCHIUM_IDENTITY

SLIDE_REPAIR_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：根据审核反馈，修订单页 SlideSpec 的标题、核心信息与要点。

专业原则：
- 保留原页叙事意图，只修复审核指出的问题。
- 核心信息保持一句完整结论，不要写成段落。
- 要点不超过 5 条，每条简洁有力。
- 不编造项目数据；缺失信息用「待确认」表述。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。

输出必须是合法 JSON，字段包括：title, message, key_points
"""


def build_slide_repair_user_prompt(
    *,
    slide_summary: str,
    issue_summary: str,
    brief_summary: str,
) -> str:
    return (
        "请根据审核反馈修订以下页面 JSON。\n\n"
        f"【Brief 摘要】\n{brief_summary}\n\n"
        f"【当前页面】\n{slide_summary}\n\n"
        f"【待修复问题】\n{issue_summary}\n"
    )
