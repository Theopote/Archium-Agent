"""Explainable Pillow-based visual QA checks for architectural drawings."""

from __future__ import annotations

import re
from collections import Counter
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

from uuid import UUID

from archium.domain.visual_qa import VisualQACheck, VisualQAReport
from archium.infrastructure.vision.analyzer_version import ANALYZER_VERSION

_MIN_PRESENTATION_WIDTH = 800
_MIN_PRESENTATION_HEIGHT = 600
_EXCESSIVE_MARGIN_RATIO = 0.18
_LOW_CONTRAST_STDEV = 28.0
_EDGE_CLIP_DARK_RATIO = 0.08
_HIGH_TEXT_EDGE_DENSITY = 0.14
_LEGEND_MIN_COLOR_PATCHES = 3
_NORTH_ARROW_MIN_SCORE = 0.28

_DRAWING_TYPES = ("site_plan", "floor_plan", "section", "elevation", "diagram", "photo")


def analyze_image(asset_id: UUID, asset_path: str, image: Image.Image) -> VisualQAReport:
    """Run all lightweight visual checks and return an explainable report."""
    width, height = image.size
    checks: list[VisualQACheck] = []
    checks.append(check_dimensions(image))
    checks.append(check_blank_margins(image))
    checks.append(check_dominant_colors(image))
    checks.append(check_edge_clipping(image))
    checks.append(check_text_density(image))
    checks.append(check_north_arrow(image))
    checks.append(check_legend_region(image))

    drawing_type, confidence, classifier_evidence = classify_drawing(image)
    checks.append(
        VisualQACheck(
            check_name="drawing_classifier",
            passed=True,
            confidence=confidence,
            summary=f"图像分类倾向为 {drawing_type}",
            evidence=classifier_evidence,
        )
    )

    return VisualQAReport(
        asset_id=asset_id,
        asset_path=asset_path,
        width=width,
        height=height,
        analyzer_version=ANALYZER_VERSION,
        drawing_type=drawing_type,
        drawing_type_confidence=confidence,
        checks=checks,
    )


def check_dimensions(image: Image.Image) -> VisualQACheck:
    width, height = image.size
    passed = width >= _MIN_PRESENTATION_WIDTH and height >= _MIN_PRESENTATION_HEIGHT
    return VisualQACheck(
        check_name="image_dimensions",
        passed=passed,
        confidence=1.0 if not passed else 1.0,
        summary=(
            f"分辨率 {width}×{height} 满足汇报展示要求"
            if passed
            else f"分辨率 {width}×{height} 低于建议下限 {_MIN_PRESENTATION_WIDTH}×{_MIN_PRESENTATION_HEIGHT}"
        ),
        method="pillow_heuristic",
        threshold=float(_MIN_PRESENTATION_WIDTH),
        evidence={
            "width": width,
            "height": height,
            "aspect_ratio": round(width / height, 3) if height else None,
            "min_width": _MIN_PRESENTATION_WIDTH,
            "min_height": _MIN_PRESENTATION_HEIGHT,
        },
    )


def check_blank_margins(image: Image.Image) -> VisualQACheck:
    gray = ImageOps.grayscale(image)
    width, height = gray.size
    border_x = max(1, int(width * 0.05))
    border_y = max(1, int(height * 0.05))
    center = gray.crop((border_x, border_y, width - border_x, height - border_y))
    center_mean = ImageStat.Stat(center).mean[0]

    margin_scores: dict[str, float] = {}
    for name, box in (
        ("top", (0, 0, width, border_y)),
        ("bottom", (0, height - border_y, width, height)),
        ("left", (0, 0, border_x, height)),
        ("right", (width - border_x, 0, width, height)),
    ):
        region = gray.crop(box)
        margin_scores[name] = abs(ImageStat.Stat(region).mean[0] - center_mean)

    max_margin = max(margin_scores.values()) if margin_scores else 0.0
    margin_ratio = max_margin / 255.0
    passed = margin_ratio < _EXCESSIVE_MARGIN_RATIO
    return VisualQACheck(
        check_name="blank_margins",
        passed=passed,
        confidence=min(1.0, margin_ratio / _EXCESSIVE_MARGIN_RATIO),
        summary=(
            "页边留白比例正常"
            if passed
            else "检测到过大空白边距，有效图面占比偏低"
        ),
        method="pillow_heuristic",
        threshold=_EXCESSIVE_MARGIN_RATIO,
        evidence={
            "margin_contrast_by_edge": {key: round(value, 2) for key, value in margin_scores.items()},
            "margin_ratio": round(margin_ratio, 3),
            "threshold": _EXCESSIVE_MARGIN_RATIO,
        },
    )


def check_dominant_colors(image: Image.Image) -> VisualQACheck:
    sample = image.copy()
    sample.thumbnail((256, 256))
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = Counter(quantized.getdata())
    ranked: list[dict[str, object]] = []
    total = sum(counts.values()) or 1
    for color_index, count in counts.most_common(5):
        offset = color_index * 3
        if offset + 2 >= len(palette):
            continue
        rgb = (palette[offset], palette[offset + 1], palette[offset + 2])
        ranked.append(
            {
                "rgb": rgb,
                "hex": "#{:02x}{:02x}{:02x}".format(*rgb),
                "share": round(count / total, 3),
            }
        )

    gray = ImageOps.grayscale(image)
    stdev = ImageStat.Stat(gray).stddev[0]
    passed = stdev >= _LOW_CONTRAST_STDEV
    return VisualQACheck(
        check_name="dominant_colors",
        passed=passed,
        confidence=min(1.0, stdev / _LOW_CONTRAST_STDEV),
        summary=(
            "图像对比度充足，主色分布清晰"
            if passed
            else "图像整体对比度偏低，流线或文字可能不够清晰"
        ),
        method="pillow_heuristic",
        threshold=_LOW_CONTRAST_STDEV,
        evidence={
            "luminance_stdev": round(stdev, 2),
            "threshold_stdev": _LOW_CONTRAST_STDEV,
            "dominant_colors": ranked,
        },
    )


def check_edge_clipping(image: Image.Image) -> VisualQACheck:
    gray = ImageOps.grayscale(image)
    width, height = gray.size
    edge = max(1, int(min(width, height) * 0.02))
    dark_threshold = 210

    edge_ratios: dict[str, float] = {}
    for name, box in (
        ("top", (0, 0, width, edge)),
        ("bottom", (0, height - edge, width, height)),
        ("left", (0, 0, edge, height)),
        ("right", (width - edge, 0, width, height)),
    ):
        region = gray.crop(box)
        pixels = list(region.getdata())
        dark = sum(1 for value in pixels if value < dark_threshold)
        edge_ratios[name] = dark / max(len(pixels), 1)

    max_ratio = max(edge_ratios.values()) if edge_ratios else 0.0
    passed = max_ratio < _EDGE_CLIP_DARK_RATIO
    clipped_edges = [name for name, ratio in edge_ratios.items() if ratio >= _EDGE_CLIP_DARK_RATIO]
    return VisualQACheck(
        check_name="edge_clipping",
        passed=passed,
        confidence=min(1.0, max_ratio / _EDGE_CLIP_DARK_RATIO),
        summary=(
            "未发现明显贴边裁切"
            if passed
            else f"图面内容可能贴边裁切：{', '.join(clipped_edges)}"
        ),
        method="pillow_heuristic",
        threshold=_EDGE_CLIP_DARK_RATIO,
        evidence={
            "dark_pixel_ratio_by_edge": {key: round(value, 3) for key, value in edge_ratios.items()},
            "threshold": _EDGE_CLIP_DARK_RATIO,
            "clipped_edges": clipped_edges,
        },
    )


def check_text_density(image: Image.Image) -> VisualQACheck:
    ocr_chars, ocr_engine = _try_ocr_char_count(image)
    gray = ImageOps.grayscale(image)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_pixels = list(edges.getdata())
    edge_density = sum(1 for value in edge_pixels if value > 40) / max(len(edge_pixels), 1)

    if ocr_chars is not None:
        area = gray.size[0] * gray.size[1]
        char_density = ocr_chars / max(area / 10_000, 1)
        passed = char_density < 120
        return VisualQACheck(
            check_name="text_density",
            passed=passed,
            confidence=min(1.0, char_density / 120),
            summary=(
                f"OCR 识别约 {ocr_chars} 字符，文字密度正常"
                if passed
                else f"OCR 识别约 {ocr_chars} 字符，图纸文字可能过小或过多"
            ),
            evidence={
                "ocr_engine": ocr_engine,
                "ocr_char_count": ocr_chars,
                "char_density_per_10k_px": round(char_density, 2),
                "edge_density": round(edge_density, 3),
            },
            method="ocr_char_density" if ocr_engine else "pillow_heuristic",
            threshold=120.0,
        )

    passed = edge_density < _HIGH_TEXT_EDGE_DENSITY
    return VisualQACheck(
        check_name="text_density",
        passed=passed,
        confidence=min(1.0, edge_density / _HIGH_TEXT_EDGE_DENSITY),
        summary=(
            "边缘密度正常，未见明显文字拥挤"
            if passed
            else "边缘密度偏高，可能存在过小文字或密集标注"
        ),
        method="edge_density_proxy",
        threshold=_HIGH_TEXT_EDGE_DENSITY,
        evidence={
            "ocr_engine": None,
            "edge_density": round(edge_density, 3),
            "threshold": _HIGH_TEXT_EDGE_DENSITY,
            "method": "edge_density_proxy",
        },
    )


def check_north_arrow(image: Image.Image) -> VisualQACheck:
    width, height = image.size
    corner_size = max(24, int(min(width, height) * 0.18))
    corners = {
        "top_right": (width - corner_size, 0, width, corner_size),
        "top_left": (0, 0, corner_size, corner_size),
    }
    gray = ImageOps.grayscale(image)
    scores: dict[str, float] = {}
    for name, box in corners.items():
        region = gray.crop(box)
        scores[name] = _corner_symbol_score(region)

    best_corner = max(scores, key=lambda corner: scores[corner])
    best_score = scores[best_corner]
    passed = best_score >= _NORTH_ARROW_MIN_SCORE
    return VisualQACheck(
        check_name="north_arrow",
        passed=passed,
        confidence=best_score,
        summary=(
            f"在 {best_corner} 区域检测到可能的指北针特征"
            if passed
            else "未在图角区域检测到指北针/北向符号"
        ),
        method="pillow_heuristic",
        threshold=_NORTH_ARROW_MIN_SCORE,
        evidence={
            "corner_scores": {key: round(value, 3) for key, value in scores.items()},
            "best_corner": best_corner,
            "threshold": _NORTH_ARROW_MIN_SCORE,
        },
    )


def check_legend_region(image: Image.Image) -> VisualQACheck:
    width, height = image.size
    strip_h = max(24, int(height * 0.22))
    strip_w = max(24, int(width * 0.22))
    regions = {
        "bottom_strip": (0, height - strip_h, width, height),
        "right_strip": (width - strip_w, 0, width, height),
        "bottom_right": (width - strip_w, height - strip_h, width, height),
    }

    best_region = ""
    best_score = 0.0
    best_patches = 0
    for name, box in regions.items():
        score, patches = _legend_score(image.crop(box))
        if score > best_score:
            best_region = name
            best_score = score
            best_patches = patches

    passed = best_patches >= _LEGEND_MIN_COLOR_PATCHES and best_score >= 0.4
    return VisualQACheck(
        check_name="legend_region",
        passed=passed,
        confidence=best_score,
        summary=(
            f"在 {best_region} 检测到可能的图例色块区域"
            if passed
            else "未检测到有足够色块分区的图例区域"
        ),
        method="pillow_heuristic",
        threshold=0.4,
        evidence={
            "best_region": best_region,
            "color_patch_count": best_patches,
            "legend_score": round(best_score, 3),
            "min_color_patches": _LEGEND_MIN_COLOR_PATCHES,
        },
    )


def classify_drawing(image: Image.Image) -> tuple[str, float, dict[str, object]]:
    width, height = image.size
    aspect = width / height if height else 1.0
    gray = ImageOps.grayscale(image)
    stdev = ImageStat.Stat(gray).stddev[0]
    edge = gray.filter(ImageFilter.FIND_EDGES)
    edge_ratio = sum(1 for value in edge.getdata() if value > 35) / max(width * height, 1)

    sample = image.copy()
    sample.thumbnail((128, 128))
    color_count = len(set(sample.quantize(colors=12, method=Image.Quantize.MEDIANCUT).getdata()))

    scores = {
        "site_plan": _score_site_plan(aspect, edge_ratio, color_count),
        "floor_plan": _score_floor_plan(aspect, edge_ratio, stdev),
        "section": _score_section(aspect, edge_ratio, stdev),
        "elevation": _score_elevation(aspect, edge_ratio, stdev),
        "diagram": _score_diagram(edge_ratio, color_count),
        "photo": _score_photo(stdev, color_count, edge_ratio),
    }
    drawing_type = max(scores, key=lambda label: scores[label])
    confidence = scores[drawing_type]
    return drawing_type, round(confidence, 3), {
        "scores": {key: round(value, 3) for key, value in scores.items()},
        "aspect_ratio": round(aspect, 3),
        "edge_ratio": round(edge_ratio, 4),
        "color_count": color_count,
        "luminance_stdev": round(stdev, 2),
    }


def _try_ocr_char_count(image: Image.Image) -> tuple[int | None, str | None]:
    try:
        import pytesseract
    except ImportError:
        return None, None
    text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    normalized = re.sub(r"\s+", "", text)
    return len(normalized), "pytesseract"


def _corner_symbol_score(region: Image.Image) -> float:
    width, height = region.size
    if width < 8 or height < 8:
        return 0.0
    edges = region.filter(ImageFilter.FIND_EDGES)
    edge_ratio = sum(1 for value in edges.getdata() if value > 45) / max(width * height, 1)
    dark_ratio = sum(1 for value in region.getdata() if value < 120) / max(width * height, 1)
    upper_focus = region.crop((0, 0, width, max(1, height // 2)))
    upper_edges = upper_focus.filter(ImageFilter.FIND_EDGES)
    upper_ratio = sum(1 for value in upper_edges.getdata() if value > 45) / max(width * max(1, height // 2), 1)
    return min(1.0, edge_ratio * 4 + dark_ratio * 0.8 + upper_ratio * 2)


def _legend_score(region: Image.Image) -> tuple[float, int]:
    sample = region.copy()
    sample.thumbnail((160, 120))
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    counts = Counter(quantized.getdata())
    significant = [count for count in counts.values() if count >= max(20, (sample.size[0] * sample.size[1]) // 200)]
    patch_count = len(significant)
    edge = ImageOps.grayscale(sample).filter(ImageFilter.FIND_EDGES)
    box_lines = sum(1 for value in edge.getdata() if value > 50) / max(sample.size[0] * sample.size[1], 1)
    score = min(1.0, patch_count / 6 + box_lines * 2)
    return score, patch_count


def _score_site_plan(aspect: float, edge_ratio: float, color_count: int) -> float:
    aspect_score = 1.0 - min(abs(aspect - 1.2) / 1.2, 1.0)
    return 0.35 * aspect_score + 0.35 * min(edge_ratio * 8, 1.0) + 0.3 * min(color_count / 10, 1.0)


def _score_floor_plan(aspect: float, edge_ratio: float, stdev: float) -> float:
    aspect_score = 1.0 - min(abs(aspect - 1.0) / 1.0, 1.0)
    return 0.3 * aspect_score + 0.45 * min(edge_ratio * 10, 1.0) + 0.25 * min(stdev / 60, 1.0)


def _score_section(aspect: float, edge_ratio: float, stdev: float) -> float:
    vertical_score = 1.0 - min(abs(aspect - 0.75) / 0.75, 1.0)
    return 0.45 * vertical_score + 0.35 * min(edge_ratio * 9, 1.0) + 0.2 * min(stdev / 55, 1.0)


def _score_elevation(aspect: float, edge_ratio: float, stdev: float) -> float:
    horizontal_score = 1.0 - min(abs(aspect - 1.4) / 1.4, 1.0)
    return 0.45 * horizontal_score + 0.35 * min(edge_ratio * 8, 1.0) + 0.2 * min(stdev / 55, 1.0)


def _score_diagram(edge_ratio: float, color_count: int) -> float:
    return 0.55 * min(edge_ratio * 12, 1.0) + 0.45 * min(color_count / 8, 1.0)


def _score_photo(stdev: float, color_count: int, edge_ratio: float) -> float:
    return 0.4 * min(stdev / 70, 1.0) + 0.35 * min(color_count / 12, 1.0) + 0.25 * (1.0 - min(edge_ratio * 10, 1.0))
