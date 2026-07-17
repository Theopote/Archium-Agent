"""Marp CLI end-to-end smoke test — real PPTX/PDF/PNG export."""

from __future__ import annotations

import shutil
from pathlib import Path

import fitz
import pytest
from archium.config.settings import Settings
from archium.infrastructure.renderers.marp_cli import MarpCliRunner
from pptx import Presentation

pytestmark = [pytest.mark.smoke, pytest.mark.marp_smoke]

_MARKDOWN_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "marp" / "smoke.presentation.md"
_ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
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

    pptx_path = (tmp_path / "smoke.presentation.pptx").resolve()
    pdf_path = (tmp_path / "smoke.presentation.pdf").resolve()
    preview_dir = (tmp_path / "previews").resolve()

    runner.convert(markdown_path, pptx_path)
    runner.convert(markdown_path, pdf_path)
    images = runner.export_images(markdown_path, output_dir=preview_dir, image_format="png")

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

    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_pptx = _ARTIFACT_DIR / "marp_smoke.presentation.pptx"
    artifact_pdf = _ARTIFACT_DIR / "marp_smoke.presentation.pdf"
    artifact_pptx.write_bytes(pptx_path.read_bytes())
    artifact_pdf.write_bytes(pdf_path.read_bytes())
    for index, image in enumerate(images, start=1):
        target = _ARTIFACT_DIR / f"marp_smoke.presentation.{index}.png"
        target.write_bytes(image.read_bytes())


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_marp_cli_available_when_installed() -> None:
    if not shutil.which("marp"):
        pytest.skip("Marp CLI not installed globally")
    assert _runner_available()
