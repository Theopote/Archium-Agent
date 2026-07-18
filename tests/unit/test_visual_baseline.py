"""Unit tests for visual baseline comparison (no Marp required)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from tests.golden.visual.baseline import (
    BaselineManifest,
    PreviewSnapshot,
    SlideSnapshot,
    average_hash_hex,
    compare_preview_image,
    compare_structure,
    hamming_hex,
)


def _solid(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (320, 180)) -> Path:
    image = Image.new("RGB", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def test_average_hash_is_stable_for_identical_images(tmp_path: Path) -> None:
    path = _solid(tmp_path / "a.png", (240, 240, 240))
    with Image.open(path) as image:
        first = average_hash_hex(image)
        second = average_hash_hex(image)
    assert first == second
    assert hamming_hex(first, first) == 0


def test_compare_preview_image_flags_large_layout_change(tmp_path: Path) -> None:
    baseline_path = _solid(tmp_path / "baseline.png", (250, 250, 250))
    actual_path = _solid(tmp_path / "actual.png", (20, 20, 20))
    with Image.open(baseline_path) as image:
        expected_hash = average_hash_hex(image)
    issues = compare_preview_image(baseline_path, actual_path, expected_hash=expected_hash)
    assert issues
    assert any("layout hash drift" in issue or "pixel diff" in issue for issue in issues)


def test_compare_structure_detects_page_count_mismatch() -> None:
    from uuid import uuid4

    from archium.domain.enums import SlideType
    from archium.domain.slide import SlideSpec

    presentation_id = uuid4()
    baseline = BaselineManifest(
        case_id="case_a_hospital",
        marp_theme="default",
        slide_count=2,
        preview_count=2,
        slides=(
            SlideSnapshot(0, "封面", SlideType.TITLE.value, "default", True),
            SlideSnapshot(1, "论点", SlideType.CONTENT.value, "default", True),
        ),
        previews=(
            PreviewSnapshot("slide_01.png", 320, 180, "0" * 16),
            PreviewSnapshot("slide_02.png", 320, 180, "0" * 16),
        ),
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="封面",
            message="核心结论",
            slide_type=SlideType.TITLE,
        ),
    ]
    issues = compare_structure(baseline, slides=slides, preview_paths=[Path("a.png")])
    assert any("slide count changed" in issue for issue in issues)
    assert any("preview count changed" in issue for issue in issues)


def test_compare_preview_image_detects_margin_overflow(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.png"
    actual_path = tmp_path / "actual.png"
    base = Image.new("RGB", (400, 300), "white")
    base.save(baseline_path)

    actual = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(actual)
    draw.rectangle((360, 260, 395, 295), fill="black")
    actual.save(actual_path)

    with Image.open(baseline_path) as image:
        expected_hash = average_hash_hex(image)
    issues = compare_preview_image(baseline_path, actual_path, expected_hash=expected_hash)
    assert any("margin overflow" in issue for issue in issues)
