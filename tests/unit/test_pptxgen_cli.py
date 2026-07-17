"""Unit tests for PptxGenJS CLI runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from archium.config.settings import Settings
from archium.exceptions import RenderingError
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner


def test_pptxgen_cli_render_invokes_node(tmp_path: Path) -> None:
    spec_path = tmp_path / "presentation.spec.json"
    spec_path.write_text('{"title":"Test","slides":[]}', encoding="utf-8")
    output_path = tmp_path / "presentation.editable.pptx"
    script_path = tmp_path / "render.mjs"
    script_path.write_text("// mock", encoding="utf-8")
    node_modules = tmp_path / "node_modules" / "pptxgenjs"
    node_modules.mkdir(parents=True)
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    settings = Settings(_env_file=None, pptxgen_script_path=script_path)
    runner = PptxGenCliRunner(settings)

    completed = MagicMock(returncode=0, stdout="", stderr="")

    def _touch_output(*args: object, **kwargs: object) -> MagicMock:
        output_path.write_bytes(b"pptx")
        return completed

    with (
        patch.object(runner, "is_available", return_value=True),
        patch("archium.infrastructure.renderers.pptxgen_cli.subprocess.run", side_effect=_touch_output),
    ):
        result = runner.render(spec_path, output_path)

    assert result == output_path
    assert output_path.exists()


def test_pptxgen_cli_render_raises_when_unavailable(tmp_path: Path) -> None:
    spec_path = tmp_path / "presentation.spec.json"
    spec_path.write_text("{}", encoding="utf-8")
    runner = PptxGenCliRunner(Settings(_env_file=None))

    with (
        patch.object(runner, "is_available", return_value=False),
        pytest.raises(RenderingError, match="PptxGenJS"),
    ):
        runner.render(spec_path, tmp_path / "out.pptx")
