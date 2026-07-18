"""PptxGenJS CLI integration for editable PPTX export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from archium.config.settings import Settings, get_settings
from archium.exceptions import RenderingError


class PptxGenCliRunner:
    """Invoke the bundled Node scripts to convert JSON specs to PPTX."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def command(self) -> str:
        return self._settings.pptxgen_node_command

    @property
    def script_path(self) -> Path:
        return self._settings.resolved_pptxgen_script_path

    @property
    def layout_plan_script_path(self) -> Path:
        return self.script_path.parent / "render-plan.mjs"

    def is_available(self) -> bool:
        if shutil.which(self.command) is None:
            return False
        if not self.script_path.exists():
            return False
        return (self.script_path.parent / "node_modules" / "pptxgenjs").exists()

    def render(self, spec_path: Path, output_path: Path) -> Path:
        """Convert a PresentationSpec JSON file to an editable PPTX."""
        return self._run_script(self.script_path, spec_path, output_path)

    def render_layout_instructions(self, deck_path: Path, output_path: Path) -> Path:
        """Convert a LayoutPlan instruction deck JSON to an editable PPTX."""
        script = self.layout_plan_script_path
        if not script.exists():
            raise RenderingError(f"LayoutPlan render script not found: {script}")
        return self._run_script(script, deck_path, output_path)

    def _run_script(self, script_path: Path, input_path: Path, output_path: Path) -> Path:
        if not input_path.exists():
            raise RenderingError(f"Input file not found: {input_path}")

        if output_path.suffix.lower() != ".pptx":
            raise RenderingError("PptxGen output must use .pptx extension")

        if not self.is_available():
            install_dir = self.script_path.parent
            raise RenderingError(
                "未检测到 PptxGenJS 运行时。请先安装 Node.js，然后在项目目录运行：\n"
                f"  cd {install_dir}\n"
                "  npm install\n"
                f"安装完成后执行 `{self.command} --version` 验证。"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_input = input_path.resolve()
        resolved_output = output_path.resolve()
        result = subprocess.run(
            [
                self.command,
                str(script_path),
                "--input",
                str(resolved_input),
                "--output",
                str(resolved_output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(script_path.parent),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RenderingError(f"PptxGenJS 导出失败：{detail or '未知错误'}")
        if not output_path.exists():
            raise RenderingError("PptxGenJS 未生成 PPTX 文件")
        return resolved_output
