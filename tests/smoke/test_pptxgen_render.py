"""PptxGenJS end-to-end smoke test — real Node render + python-pptx verification."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from archium.config.settings import Settings
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from pptx import Presentation

pytestmark = pytest.mark.smoke

_SPEC_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "pptxgen" / "smoke.spec.json"
_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
_PPTXGEN_DIR = (
    Path(__file__).resolve().parents[2]
    / "archium"
    / "infrastructure"
    / "renderers"
    / "pptxgen"
)


def _runner_available() -> bool:
    runner = PptxGenCliRunner(Settings(_env_file=None))
    return runner.is_available()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_pptxgen_smoke_render_and_reopen(tmp_path: Path) -> None:
    if not _runner_available():
        pytest.skip("PptxGenJS runtime unavailable — run npm install in archium/infrastructure/renderers/pptxgen")

    output_path = tmp_path / "smoke.editable.pptx"
    runner = PptxGenCliRunner(Settings(_env_file=None))
    rendered = runner.render(_SPEC_PATH, output_path)

    assert rendered.exists()
    assert rendered.stat().st_size > 500

    presentation = Presentation(rendered)
    assert len(presentation.slides) == 2

    first = presentation.slides[0]
    assert first.shapes.title is not None
    assert "Archium PptxGen Smoke" in first.shapes.title.text

    first_notes = first.notes_slide.notes_text_frame.text
    assert "Smoke test speaker note" in first_notes

    second = presentation.slides[1]
    assert second.shapes.title is not None
    assert "要点页" in second.shapes.title.text
    second_notes = second.notes_slide.notes_text_frame.text
    assert "中文路径" in second_notes

    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = _ARTIFACT_DIR / "pptxgen_smoke.editable.pptx"
    artifact_path.write_bytes(rendered.read_bytes())
    assert artifact_path.stat().st_size > 500


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_pptxgen_node_modules_present() -> None:
    node_modules = _PPTXGEN_DIR / "node_modules" / "pptxgenjs"
    if not node_modules.exists():
        pytest.skip("pptxgenjs not installed — run npm install in pptxgen directory")
    assert (_PPTXGEN_DIR / "render.mjs").exists()
