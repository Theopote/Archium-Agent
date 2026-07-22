"""Pillow heuristics for page-level screenshot QA (WP H §11.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

try:
    from PIL import Image, ImageFilter, ImageOps, ImageStat
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]

from archium.domain.visual.scene_qa import PostRenderCheckCode
from archium.infrastructure.vision.pillow_pixels import iter_image_pixels

_BLANK_STDEV = 12.0
_BLANK_NEAR_WHITE_RATIO = 0.92
_BLACK_BLOCK_RATIO = 0.22
_FLAT_GRAY_RATIO = 0.35
_FLAT_EDGE_MAX = 0.04
_BLUR_LAPLACIAN_VAR = 18.0
_HASH_DISTANCE_DUP = 6
_PNG_PPTX_MSE = 1800.0


@dataclass
class ScreenshotCheck:
    check_code: str
    passed: bool
    severity: str
    title: str
    description: str
    suggestion: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)


def analyze_slide_screenshot(image: Image.Image) -> list[ScreenshotCheck]:
    """Run per-page screenshot heuristics."""
    if Image is None:  # pragma: no cover
        return []
    checks: list[ScreenshotCheck] = []
    gray = ImageOps.grayscale(image)
    checks.append(check_blank_page(gray))
    checks.append(check_black_block(gray))
    checks.append(check_image_not_loaded(gray))
    checks.append(check_drawing_blur(gray))
    return checks


def check_blank_page(gray: Image.Image) -> ScreenshotCheck:
    stats = ImageStat.Stat(gray)
    stdev = float(stats.stddev[0]) if stats.stddev else 0.0
    mean = float(stats.mean[0]) if stats.mean else 0.0
    hist = gray.histogram()
    near_white = sum(hist[240:]) / max(1, sum(hist))
    passed = not (stdev < _BLANK_STDEV and near_white >= _BLANK_NEAR_WHITE_RATIO)
    return ScreenshotCheck(
        check_code=PostRenderCheckCode.BLANK_PAGE,
        passed=passed,
        severity="high",
        title="渲染页接近空白",
        description=(
            f"页面灰度方差 {stdev:.1f}、近白占比 {near_white:.0%}，疑似空白页。"
            if not passed
            else "页面内容密度正常。"
        ),
        suggestion="检查导出链路或素材是否全部未渲染。" if not passed else None,
        evidence={"stdev": stdev, "mean": mean, "near_white_ratio": round(near_white, 3)},
    )


def check_black_block(gray: Image.Image) -> ScreenshotCheck:
    hist = gray.histogram()
    total = max(1, sum(hist))
    near_black = sum(hist[:20]) / total
    passed = near_black < _BLACK_BLOCK_RATIO
    return ScreenshotCheck(
        check_code=PostRenderCheckCode.BLACK_BLOCK,
        passed=passed,
        severity="high",
        title="渲染页存在大面积黑块",
        description=(
            f"近黑像素占比 {near_black:.0%}，可能存在渲染失败黑块。"
            if not passed
            else "未检测到大面积黑块。"
        ),
        suggestion="检查字体/图片解码或背景填充。" if not passed else None,
        evidence={"near_black_ratio": round(near_black, 3)},
    )


def check_image_not_loaded(gray: Image.Image) -> ScreenshotCheck:
    """Detect large flat mid-gray regions with low edge density (placeholder-like)."""
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
    hist = gray.histogram()
    total = max(1, sum(hist))
    mid_gray = sum(hist[110:160]) / total
    flat = mid_gray >= _FLAT_GRAY_RATIO and edge_mean < _FLAT_EDGE_MAX * 255
    return ScreenshotCheck(
        check_code=PostRenderCheckCode.IMAGE_NOT_LOADED,
        passed=not flat,
        severity="medium",
        title="渲染页疑似图片未加载",
        description=(
            f"中灰平坦区占比 {mid_gray:.0%}、边缘均值 {edge_mean:.1f}，疑似占位未加载图。"
            if flat
            else "未检测到典型未加载占位。"
        ),
        suggestion="确认图片路径与渲染器资源嵌入。" if flat else None,
        evidence={"mid_gray_ratio": round(mid_gray, 3), "edge_mean": round(edge_mean, 2)},
    )


def check_drawing_blur(gray: Image.Image) -> ScreenshotCheck:
    # Laplacian variance via FIND_EDGES + variance proxy
    edges = gray.filter(ImageFilter.FIND_EDGES)
    stats = ImageStat.Stat(edges)
    variance = float(stats.var[0]) if stats.var else 0.0
    passed = variance >= _BLUR_LAPLACIAN_VAR
    return ScreenshotCheck(
        check_code=PostRenderCheckCode.DRAWING_BLUR,
        passed=passed,
        severity="suggestion",
        title="渲染页图面过于模糊",
        description=(
            f"边缘方差 {variance:.1f} 偏低，图面可能模糊。"
            if not passed
            else "图面锐度可接受。"
        ),
        suggestion="使用更高分辨率图纸或避免过度缩放。" if not passed else None,
        evidence={"edge_variance": round(variance, 2)},
    )


def average_hash(image: Image.Image, *, size: int = 8) -> int:
    """Simple aHash for duplicate-page detection."""
    gray = ImageOps.grayscale(image).resize((size, size))
    pixels = list(iter_image_pixels(gray))
    avg = sum(pixels) / max(1, len(pixels))
    bits = 0
    for index, value in enumerate(pixels):
        if value >= avg:
            bits |= 1 << index
    return bits


def hash_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def compare_png_pptx_screenshots(png: Image.Image, pptx_shot: Image.Image) -> ScreenshotCheck:
    """Mean-squared error style difference between two page screenshots."""
    left = ImageOps.grayscale(png).resize((160, 90))
    right = ImageOps.grayscale(pptx_shot).resize((160, 90))
    lp = list(iter_image_pixels(left))
    rp = list(iter_image_pixels(right))
    mse = sum((a - b) ** 2 for a, b in zip(lp, rp, strict=True)) / max(1, len(lp))
    passed = mse < _PNG_PPTX_MSE
    return ScreenshotCheck(
        check_code=PostRenderCheckCode.PNG_PPTX_DIFF,
        passed=passed,
        severity="medium",
        title="PNG 与 PPTX 截图差异过大",
        description=(
            f"PNG/PPTX 截图 MSE={mse:.0f}，超过阈值 {_PNG_PPTX_MSE:.0f}。"
            if not passed
            else f"PNG/PPTX 截图差异可接受（MSE={mse:.0f}）。"
        ),
        suggestion="检查双渲染器节点一致性。" if not passed else None,
        evidence={"mse": round(mse, 1)},
    )


def load_image(path: Path) -> Image.Image | None:
    if Image is None or not path.is_file():  # pragma: no cover
        return None
    try:
        with Image.open(path) as opened:
            return opened.convert("RGB")
    except (OSError, Image.DecompressionBombError):
        return None
