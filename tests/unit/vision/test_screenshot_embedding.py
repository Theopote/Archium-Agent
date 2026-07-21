"""Tests for deterministic screenshot embeddings."""

from __future__ import annotations

from pathlib import Path

import pytest

from archium.infrastructure.vision.screenshot_embedding import (
    compute_screenshot_embedding_from_image,
    screenshot_embedding_available,
    try_compute_screenshot_embedding,
)

pytest.importorskip("PIL")


def test_same_image_produces_identical_embedding(tmp_path: Path) -> None:
    if not screenshot_embedding_available():
        pytest.skip("Pillow not available")
    from PIL import Image

    img = Image.new("RGB", (320, 180), color=(240, 240, 240))
    path = tmp_path / "slide.png"
    img.save(path)
    a = try_compute_screenshot_embedding(path)
    b = try_compute_screenshot_embedding(path)
    assert a is not None
    assert a == b
    assert len(a) >= 40


def test_different_images_produce_different_embeddings() -> None:
    if not screenshot_embedding_available():
        pytest.skip("Pillow not available")
    from PIL import Image

    left = Image.new("RGB", (320, 180), color=(20, 20, 20))
    right = Image.new("RGB", (320, 180), color=(240, 240, 240))
    emb_left = compute_screenshot_embedding_from_image(left)
    emb_right = compute_screenshot_embedding_from_image(right)
    assert emb_left != emb_right


def test_band_energy_reflects_vertical_layout() -> None:
    if not screenshot_embedding_available():
        pytest.skip("Pillow not available")
    from PIL import Image

    img = Image.new("RGB", (320, 180), color=(255, 255, 255))
    for x in range(320):
        for y in range(60):
            img.putpixel((x, y), (0, 0, 0))
    emb = compute_screenshot_embedding_from_image(img)
    assert emb[0] < emb[10]
