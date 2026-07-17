import re
import shutil
import subprocess
from pathlib import Path

from config import ARCHIUM_IDENTITY, GEMINI_MODEL, client

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


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _generate_markdown(topic: str) -> str:
    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请为主题「{topic}」制作一份 8–12 页的演示文稿。"},
        ],
    )
    return _strip_code_fence(response.choices[0].message.content or "")


def _run_marp(markdown_path: Path, output_path: Path) -> None:
    if shutil.which("marp") is None:
        raise RuntimeError(
            "未检测到 Marp CLI。请先安装 Node.js，然后运行：\n"
            "  npm install -g @marp-team/marp-cli\n"
            "安装完成后执行 `marp --version` 验证。"
        )

    result = subprocess.run(
        ["marp", str(markdown_path), "-o", str(output_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Marp 转换失败：{detail or '未知错误'}")


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

    _run_marp(temp_md, out)
    return out
