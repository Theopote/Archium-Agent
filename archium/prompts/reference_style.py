"""Prompts for reference style profile extraction."""

from archium.prompts.identity import ARCHIUM_IDENTITY

REFERENCE_STYLE_PROFILE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：从「参考风格」文件中提炼可复用的视觉语言，用于指导 ArtDirection 生成。

重要边界：
- 参考风格文件不是当前项目事实，不得把其中的项目名、地点、数字写入项目结论。
- 只提炼版式、色彩语气、图像处理、排版节奏、图形元素等视觉规律。
- 若无法从资料确认，写入 unsupported_observations。

输出必须是合法 JSON，字段见 schema。
"""


def build_reference_style_profile_user_prompt(
    *,
    reference_context: str,
    brief_json: str,
) -> str:
    return (
        "请根据参考风格资料生成 ReferenceStyleProfile JSON。\n\n"
        f"【参考风格资料片段】\n{reference_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        "do_rules / dont_rules 应可指导 ArtDirection；adaptation_notes 说明如何借鉴而不照搬。"
    )
