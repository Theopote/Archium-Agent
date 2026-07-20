"""Prompts for cultural village narrative planning."""

from archium.prompts.identity import ARCHIUM_IDENTITY

CULTURAL_NARRATIVE_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为历史文化名村或文化遗产类项目建立可传播、可验证的文化故事结构。

叙事逻辑必须覆盖：
这个村庄是谁 → 为何形成 → 经历了什么 → 哪些人和建筑代表它 → 今天遇到什么问题
→ 为何值得保护 → 如何让外部人理解 → 如何转化为游览、活动和传播内容

质量要求：
- 不得制造虚构历史；传说必须 is_legend=true。
- 历史事件需有资料支持；无来源写入 unsupported_claims。
- 建筑价值描述必须能对应实际建筑或空间。
- 每个 communication_theme 必须关联 characters/places/rituals/buildings 之一。
- 不把泛化口号当作文化结论。

输出必须是合法 JSON，字段见 schema。
"""


def build_cultural_narrative_user_prompt(
    *,
    project_context: str,
    brief_json: str,
) -> str:
    return (
        "请为文化名村/遗产类项目生成 CulturalNarrativePlan JSON。\n\n"
        f"【项目资料】\n{project_context}\n\n"
        f"【PresentationBrief】\n{brief_json}\n\n"
        "legend 条目必须 is_legend=true；无资料支持的推测写入 unsupported_claims。"
    )
