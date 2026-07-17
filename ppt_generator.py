import subprocess
from pathlib import Path

from archium.infrastructure.llm import LLMRequest, get_llm_provider
from archium.infrastructure.renderers.marp_cli import MarpCliRunner
from archium.prompts.identity import ARCHIUM_IDENTITY

SYSTEM_PROMPT = ARCHIUM_IDENTITY + """\
当前任务：以建筑师汇报的专业标准，根据用户给出的主题，撰写一份完整的 Marp Markdown 幻灯片。

输出要求：
1. 必须以 Marp front matter 开头，包含 theme 与 paginate 设置，例如：
   ---
   marp: true
   theme: default
   paginate: true
   ---
2. 每张幻灯片之间用单独一行的 `---` 分隔。
3. 第一页为标题页：包含主标题、副标题（可选）、演讲者信息占位。
4. 内容页使用 `#`、`##` 标题层级，配合 `-` 列表与 **加粗** 强调要点；每页要点不超过 5 条，避免大段文字。
5. 最后一页为总结或致谢页。
6. 全文使用中文（除非主题明确要求其他语言）。
7. 只输出 Marp Markdown 正文，不要包裹在 ```markdown 代码块中，不要附加任何解释说明。
"""


def _generate_markdown(topic: str) -> str:
    provider = get_llm_provider()
    return provider.generate_text(
        LLMRequest(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"请为主题「{topic}」制作一份 8–12 页的演示文稿。",
            temperature=0.7,
        )
    )


def generate_presentation(topic: str, output_path: str) -> Path:
    """围绕 topic 生成 Marp 幻灯片并导出为 PDF 或 PPTX。"""
    if not topic.strip():
        raise ValueError("topic 不能为空")

    out = Path(output_path).resolve()
    suffix = out.suffix.lower()
    if suffix not in {".pdf", ".pptx"}:
        raise ValueError("output_path 必须以 .pdf 或 .pptx 结尾")

    out.parent.mkdir(parents=True, exist_ok=True)
    temp_md = out.parent / "temp.md"

    markdown = _generate_markdown(topic)
    temp_md.write_text(markdown, encoding="utf-8")

    MarpCliRunner().convert(temp_md, out)
    return out
