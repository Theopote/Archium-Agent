"""Marp CLI integration for exporting Markdown slides."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from archium.config.settings import Settings, get_settings
from archium.exceptions import RenderingError

_PAGE_SUFFIX_PATTERN = re.compile(r"\.(\d+)$")


class MarpCliRunner:
    """Invoke the Marp CLI to convert Markdown slides to PDF, PPTX, or images."""

    SUPPORTED_SUFFIXES = {".pdf", ".pptx"}
    SUPPORTED_IMAGE_FORMATS = {"png", "jpeg"}

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

        self._run([self.command, str(markdown_path), "-o", str(output_path)], output_path.parent)
        return output_path

    def export_images(
        self,
        markdown_path: Path,
        *,
        output_dir: Path | None = None,
        image_format: str = "png",
    ) -> list[Path]:
        """Export all slides as numbered PNG/JPEG files via ``--images``."""
        if not markdown_path.exists():
            raise RenderingError(f"Marp source file not found: {markdown_path}")

        normalized_format = image_format.lower().lstrip(".")
        if normalized_format not in self.SUPPORTED_IMAGE_FORMATS:
            raise RenderingError("Marp image output must use png or jpeg")

        target_dir = output_dir or (markdown_path.parent / "previews")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_prefix = target_dir / markdown_path.stem

        self._run(
            [
                self.command,
                str(markdown_path),
                f"--images={normalized_format}",
                "-o",
                str(output_prefix),
            ],
            target_dir,
        )

        images = sorted(
            target_dir.glob(f"{markdown_path.stem}.*.{normalized_format}"),
            key=_image_page_sort_key,
        )
        if not images:
            raise RenderingError("Marp 未生成任何预览图文件")
        return images

    def _run(self, command: list[str], output_parent: Path) -> None:
        if not self.is_available():
            raise RenderingError(
                "未检测到 Marp CLI。请先安装 Node.js，然后运行：\n"
                "  npm install -g @marp-team/marp-cli\n"
                f"安装完成后执行 `{self.command} --version` 验证。"
            )

        output_parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RenderingError(f"Marp 转换失败：{detail or '未知错误'}")


def _image_page_sort_key(path: Path) -> int:
    match = _PAGE_SUFFIX_PATTERN.search(path.stem)
    if match is None:
        return 0
    return int(match.group(1))
