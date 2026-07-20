"""Marp CLI end-to-end smoke test — real PPTX/PDF/PNG export."""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz
import pytest
from archium.config.settings import Settings
from archium.infrastructure.renderers.marp_cli import MarpCliRunner
from pptx import Presentation
from tests.smoke.artifact_publish import publish_smoke_artifact

pytestmark = [pytest.mark.smoke, pytest.mark.marp_smoke]

_MARKDOWN_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "marp" / "smoke-presentation.md"
_EXPECTED_SLIDES = 2


def _runner_available() -> bool:
    return MarpCliRunner(Settings(_env_file=None)).is_available()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_marp_smoke_exports_pptx_pdf_and_png(tmp_path: Path) -> None:
    if not _runner_available():
        pytest.skip("Marp CLI unavailable — run npm install -g @marp-team/marp-cli")

    runner = MarpCliRunner(Settings(_env_file=None))
    markdown_path = _MARKDOWN_PATH.resolve()
    assert markdown_path.exists()

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    local_markdown = work_dir / markdown_path.name
    local_markdown.write_text(markdown_path.read_text(encoding="utf-8"), encoding="utf-8")

    pptx_path = (work_dir / "smoke-presentation.pptx").resolve()
    pdf_path = (work_dir / "smoke-presentation.pdf").resolve()
    preview_dir = (work_dir / "previews").resolve()

    runner.convert(local_markdown, pptx_path)
    runner.convert(local_markdown, pdf_path)
    images = runner.export_images(local_markdown, output_dir=preview_dir, image_format="png")

    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 500
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 500
    assert len(images) == _EXPECTED_SLIDES
    assert all(image.exists() and image.stat().st_size > 100 for image in images)

    presentation = Presentation(pptx_path)
    assert len(presentation.slides) == _EXPECTED_SLIDES

    pdf_document = fitz.open(pdf_path)
    try:
        assert pdf_document.page_count == _EXPECTED_SLIDES
    finally:
        pdf_document.close()

    publish_smoke_artifact(pptx_path, "marp_smoke.presentation.pptx")
    publish_smoke_artifact(pdf_path, "marp_smoke.presentation.pdf")
    for index, image in enumerate(images, start=1):
        publish_smoke_artifact(image, f"marp_smoke.presentation.{index}.png")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_marp_cli_available_when_installed() -> None:
    if not shutil.which("marp"):
        pytest.skip("Marp CLI not installed globally")
    assert _runner_available()
