"""Unit tests for screenshot / post-render QA."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.post_render_qa_service import run_post_render_qa
from archium.domain.visual.scene_qa import PostRenderCheckCode
from archium.infrastructure.vision.screenshot_qa import (
    analyze_slide_screenshot,
    average_hash,
    hash_distance,
)
from PIL import Image


def test_blank_page_detected() -> None:
    image = Image.new("RGB", (640, 360), color=(250, 250, 250))
    checks = analyze_slide_screenshot(image)
    blank = next(check for check in checks if check.check_code == PostRenderCheckCode.BLANK_PAGE)
    assert blank.passed is False


def test_content_page_not_blank() -> None:
    image = Image.new("RGB", (640, 360), color=(240, 240, 240))
    for x in range(40, 600, 8):
        for y in range(40, 320, 8):
            image.putpixel((x, y), (20, 20, 20))
    checks = analyze_slide_screenshot(image)
    blank = next(check for check in checks if check.check_code == PostRenderCheckCode.BLANK_PAGE)
    assert blank.passed is True


def test_black_block_detected() -> None:
    image = Image.new("RGB", (640, 360), color=(0, 0, 0))
    checks = analyze_slide_screenshot(image)
    black = next(check for check in checks if check.check_code == PostRenderCheckCode.BLACK_BLOCK)
    assert black.passed is False


def test_duplicate_and_identical_pages(tmp_path: Path) -> None:
    slide_a = uuid4()
    slide_b = uuid4()
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    image = Image.new("RGB", (320, 180), color=(180, 180, 180))
    image.save(path_a)
    image.save(path_b)
    report = run_post_render_qa(
        uuid4(),
        [(slide_a, path_a), (slide_b, path_b)],
        slide_orders={slide_a: 0, slide_b: 1},
    )
    codes = {finding.check_code for finding in report.findings}
    assert PostRenderCheckCode.ALL_PAGES_IDENTICAL in codes or PostRenderCheckCode.DUPLICATE_PAGE in codes


def test_hash_distance_zero_for_same_image() -> None:
    image = Image.new("RGB", (64, 64), color=(100, 120, 140))
    digest = average_hash(image)
    assert hash_distance(digest, digest) == 0
