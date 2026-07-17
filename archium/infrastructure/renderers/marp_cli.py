"""Marp CLI integration for exporting Markdown slides."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from archium.config.settings import Settings, get_settings
from archium.exceptions import RenderingError


class MarpCliRunner:
    """Invoke the Marp CLI to convert Markdown slides to PDF or PPTX."""

    SUPPORTED_SUFFIXES = {".pdf", ".pptx"}

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def command(self) -> str:
        return self._settings.marp_command

    def is_available(self) -> bool:
        return shutil.which(self.command) is not None

    def convert(self, markdown_path: Path, output_path: Path) -> Path:
        """Convert a Marp Markdown file to PDF or PPTX."""
        if not markdown_path.exists():
            raise RenderingError(f"Marp source file not found: {markdown_path}")

        suffix = output_path.suffix.lower()
        if suffix not in self.SUPPORTED_SUFFIXES:
            raise RenderingError("Marp output must use .pdf or .pptx extension")

        if not self.is_available():
            raise RenderingError(
                "未检测到 Marp CLI。请先安装 Node.js，然后运行：\n"
                "  npm install -g @marp-team/marp-cli\n"
                f"安装完成后执行 `{self.command} --version` 验证。"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [self.command, str(markdown_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RenderingError(f"Marp 转换失败：{detail or '未知错误'}")
        return output_path
