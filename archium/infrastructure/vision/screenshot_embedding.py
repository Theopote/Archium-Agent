"""Deterministic screenshot fingerprints for template induction clustering (P2).

This is **not** a CLIP/VLM neural embedding. It compresses page PNGs into a
fixed-length vector (luminance grid + coarse color + band energy + edge density)
so visually similar slides can merge when structural JSON diverges slightly.
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageStat
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]

_GRID_W = 8
_GRID_H = 5


def screenshot_embedding_available() -> bool:
    return Image is not None


def compute_screenshot_embedding(image_path: Path | str) -> list[float]:
    """Load a slide PNG and return a portable fingerprint vector."""
    if Image is None:
        raise RuntimeError("Pillow is required for screenshot embeddings")
    path = Path(image_path)
    with Image.open(path) as handle:
        return compute_screenshot_embedding_from_image(handle.convert("RGB"))


def compute_screenshot_embedding_from_image(image: Image.Image) -> list[float]:
    """Fingerprint an in-memory RGB slide image."""
    if Image is None or ImageFilter is None or ImageStat is None:
        raise RuntimeError("Pillow is required for screenshot embeddings")

    small = image.resize((_GRID_W * 4, _GRID_H * 4), Image.Resampling.BILINEAR)
    gray = small.convert("L")
    width, height = gray.size

    grid: list[float] = []
    cell_w = width / _GRID_W
    cell_h = height / _GRID_H
    for row in range(_GRID_H):
        for col in range(_GRID_W):
            xs = int(col * cell_w)
            xe = int((col + 1) * cell_w)
            ys = int(row * cell_h)
            ye = int((row + 1) * cell_h)
            patch = gray.crop((xs, ys, xe, ye))
            mean = ImageStat.Stat(patch).mean[0]
            grid.append(round(mean / 255.0, 4))

    # Coarse RGB buckets on downsampled color image
    thumb = small.resize((_GRID_W, _GRID_H), Image.Resampling.BILINEAR)
    bucket = [0.0] * 6
    thumb_rgb = thumb.convert("RGB")
    for y in range(thumb_rgb.height):
        for x in range(thumb_rgb.width):
            pixel = thumb_rgb.getpixel((x, y))
            if not isinstance(pixel, tuple) or len(pixel) < 3:
                continue
            r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
            idx = 0
            if r >= 180:
                idx += 1
            if g >= 180:
                idx += 1
            if b >= 180:
                idx += 1
            if (r + g + b) / 3 < 80:
                idx = 5
            elif (r + g + b) / 3 > 200:
                idx = 4
            bucket[idx] += 1.0
    total = max(sum(bucket), 1.0)
    bucket = [round(v / total, 4) for v in bucket]

    bands = _band_energy(gray)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edges).mean[0] / 255.0

    return [*grid, *bucket, *bands, round(min(edge_mean, 1.0), 4)]


def _band_energy(gray: Image.Image) -> list[float]:
    width, height = gray.size
    third = max(height // 3, 1)
    bands: list[float] = []
    for y0 in range(0, height, third):
        y1 = min(y0 + third, height)
        cols = [
            gray.crop((x * width // 3, y0, (x + 1) * width // 3, y1))
            for x in range(3)
        ]
        for patch in cols:
            stat = ImageStat.Stat(patch).mean[0] / 255.0
            bands.append(round(stat, 4))
    return bands[:9]


def try_compute_screenshot_embedding(image_path: Path | str) -> list[float] | None:
    if not screenshot_embedding_available():
        return None
    path = Path(image_path)
    if not path.is_file():
        return None
    try:
        return compute_screenshot_embedding(path)
    except Exception:
        return None
