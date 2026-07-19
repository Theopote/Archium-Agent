"""Prompts for structured project fact extraction."""

from archium.prompts.identity import ARCHIUM_IDENTITY

FACT_EXTRACTION_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：从项目文档片段中提取可验证的结构化 ProjectFact。

专业原则：
- 只提取文档中明确出现或可合理归纳的项目参数（面积、层数、床位数、地点等）。
- 不要编造数据；不确定的事实不要输出。
- 每条事实必须能关联到 chunk_id 或原文引用。
- key 使用英文蛇形命名（如 site_area、bed_count）。

禁止事项：
- 不要输出 Markdown 代码块。
- 不要添加 schema 之外的字段。

输出必须是合法 JSON，字段包括：
facts: [{ key, label, value, unit, category, confidence, chunk_id, quote }]
"""


def build_fact_extraction_user_prompt(
    *,
    project_context: str,
    existing_keys: list[str] | None = None,
) -> str:
    existing_hint = ""
    if existing_keys:
        existing_hint = (
            "\n以下 key 已存在于事实账本，请勿重复输出："
            + "、".join(existing_keys)
            + "\n"
        )
    return (
        "请从以下项目资料中提取结构化事实 JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"{existing_hint}"
        "若某类信息在资料中不存在，不要猜测补写。"
    )
