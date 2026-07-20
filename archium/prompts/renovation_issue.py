"""Prompts for renovation issue map planning."""

from archium.prompts.identity import ARCHIUM_IDENTITY

RENOVATION_ISSUE_MAP_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为老旧建筑/改造类项目建立「证据 → 问题 → 策略」闭环结构。

必须覆盖的逻辑链：
现场与资料证据 → 诊断问题 → 对应改造策略 → 可进入汇报章节

质量要求：
- 每个 RenovationIssue 必须 linked_evidence_ids 指向真实 evidence_items。
- 每个 RenovationStrategy 必须 linked_issue_ids 指向已定义问题。
- 不得把推测写成已核实事实；无资料支持写入 unsupported_claims。
- 问题类别应对应改造汇报常见维度：交通、空间、立面、景观、结构、消防、节能、无障碍等。
- 策略应可对应分期实施（phasing）与范围说明（scope_note）。

输出必须是合法 JSON，字段见 schema。
"""


def build_renovation_issue_map_user_prompt(
    *,
    project_context: str,
    brief_json: str,
) -> str:
    return (
        "请为老旧建筑改造类项目生成 RenovationIssueMap JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        "确保 evidence → issue → strategy 引用关系完整；无资料支持的判断写入 unsupported_claims。"
    )
