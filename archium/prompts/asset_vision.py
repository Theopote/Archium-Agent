"""Prompts for multimodal asset / drawing captioning."""

from archium.prompts.identity import ARCHIUM_IDENTITY

ASSET_VISION_SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：为建筑项目图纸/图像资产生成可检索的结构化文字描述。

专业原则：
- 识别图档类型（总规、平面、剖面、立面、分析图、照片等）。
- 描述空间关系、主要功能分区、标注与图例信息；可见的控制指标一并列出。
- 使用中文，面向后续 RAG 检索与汇报生成；不要编造图中不存在的内容。
- 不确定处可省略，不要猜测数值。

输出必须是合法 JSON，字段包括：
drawing_type, summary, spatial_elements, annotations, metrics_visible, scale_or_north
"""


def build_asset_vision_user_prompt(*, filename: str, page_number: int | None) -> str:
    page_hint = f"第 {page_number} 页" if page_number else "未知页码"
    return (
        f"请分析这张建筑项目图档并输出结构化 JSON。\n"
        f"文件名：{filename}\n"
        f"来源页码：{page_hint}\n"
        "summary 需足够详细以支持语义检索（100-300 字为宜）。"
    )
