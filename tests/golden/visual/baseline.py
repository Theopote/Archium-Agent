"""Visual regression baseline models and comparison helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from archium.domain.slide import SlideSpec
from PIL import Image, ImageChops

BASELINE_ROOT = Path(__file__).resolve().parent / "baselines"
VISUAL_CASE_IDS: tuple[str, ...] = (
    "case_a_hospital",
    "case_b_campus",
    "case_c_competition",
)
MARP_THEME = "default"
MAX_PIXEL_DIFF_RATIO = 0.05
# Win32-approved PPTX screenshots vs Linux CI rasterizers (fonts/SVG AA) can
# sit slightly above 5%. Prefer Linux approve; this only applies on platform mismatch.
CROSS_PLATFORM_MAX_PIXEL_DIFF_RATIO = 0.06
MAX_AHASH_HAMMING = 12
MARGIN_OVERFLOW_RATIO = 0.05
MARGIN_OVERFLOW_DELTA = 0.12


@dataclass(frozen=True)
class SlideSnapshot:
    index: int
    title: str
    slide_type: str
    layout_id: str
    has_message: bool


@dataclass(frozen=True)
class PreviewSnapshot:
    file: str
    width: int
    height: int
    average_hash: str


@dataclass(frozen=True)
class BaselineManifest:
    case_id: str
    marp_theme: str
    slide_count: int
    preview_count: int
    slides: tuple[SlideSnapshot, ...]
    previews: tuple[PreviewSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "marp_theme": self.marp_theme,
            "slide_count": self.slide_count,
            "preview_count": self.preview_count,
            "slides": [asdict(item) for item in self.slides],
            "previews": [asdict(item) for item in self.previews],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BaselineManifest:
        return cls(
            case_id=str(payload["case_id"]),
            marp_theme=str(payload.get("marp_theme", MARP_THEME)),
            slide_count=int(payload["slide_count"]),
            preview_count=int(payload["preview_count"]),
            slides=tuple(SlideSnapshot(**item) for item in payload.get("slides", [])),
            previews=tuple(PreviewSnapshot(**item) for item in payload.get("previews", [])),
        )


def baseline_dir(case_id: str) -> Path:
    return BASELINE_ROOT / case_id


def manifest_path(case_id: str) -> Path:
    return baseline_dir(case_id) / "manifest.json"


def load_baseline(case_id: str) -> BaselineManifest:
    path = manifest_path(case_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BaselineManifest.from_dict(payload)


def save_baseline(case_id: str, manifest: BaselineManifest, preview_paths: list[Path]) -> Path:
    out_dir = baseline_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(preview_paths, start=1):
        target = out_dir / f"slide_{index:02d}{source.suffix or '.png'}"
        target.write_bytes(source.read_bytes())
    manifest_path(case_id).write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_dir


def average_hash_hex(image: Image.Image, *, hash_size: int = 8) -> str:
    gray = image.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    return f"{int(bits, 2):0{hash_size * hash_size // 4}x}"


def hamming_hex(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _diff_pixel_ratio(base_rgb: Image.Image, act_rgb: Image.Image, *, threshold: int = 10) -> float:
    diff = ImageChops.difference(base_rgb, act_rgb).convert("L")
    pixels = list(diff.getdata())
    differing = sum(1 for value in pixels if value > threshold)
    return differing / len(pixels) if pixels else 0.0


def _slide_snapshots(slides: list[SlideSpec]) -> tuple[SlideSnapshot, ...]:
    return tuple(
        SlideSnapshot(
            index=index,
            title=slide.title.strip(),
            slide_type=slide.slide_type.value,
            layout_id=slide.layout_id,
            has_message=bool(slide.message and slide.message.strip()),
        )
        for index, slide in enumerate(slides)
    )


def build_manifest(
    *,
    case_id: str,
    slides: list[SlideSpec],
    preview_paths: list[Path],
    marp_theme: str = MARP_THEME,
) -> BaselineManifest:
    slide_snapshots = _slide_snapshots(slides)
    preview_snapshots: list[PreviewSnapshot] = []
    for index, path in enumerate(preview_paths, start=1):
        with Image.open(path) as image:
            width, height = image.size
            preview_snapshots.append(
                PreviewSnapshot(
                    file=f"slide_{index:02d}{path.suffix or '.png'}",
                    width=width,
                    height=height,
                    average_hash=average_hash_hex(image),
                )
            )
    return BaselineManifest(
        case_id=case_id,
        marp_theme=marp_theme,
        slide_count=len(slides),
        preview_count=len(preview_paths),
        slides=slide_snapshots,
        previews=tuple(preview_snapshots),
    )


def _margin_ink_ratio(image: Image.Image, *, edge: str, margin_ratio: float) -> float:
    width, height = image.size
    margin_x = max(1, int(width * margin_ratio))
    margin_y = max(1, int(height * margin_ratio))
    gray = image.convert("L")
    pixels = gray.load()
    if edge == "bottom":
        y_start = height - margin_y
        x_start = 0
        x_end = width
        y_end = height
    elif edge == "right":
        y_start = 0
        x_start = width - margin_x
        x_end = width
        y_end = height
    else:
        raise ValueError(f"Unsupported edge: {edge}")

    dark = 0
    total = 0
    for y in range(y_start, y_end):
        for x in range(x_start, x_end):
            total += 1
            if pixels[x, y] < 235:
                dark += 1
    return dark / total if total else 0.0


def compare_preview_image(
    baseline_path: Path,
    actual_path: Path,
    *,
    expected_hash: str,
    max_pixel_diff_ratio: float = MAX_PIXEL_DIFF_RATIO,
) -> list[str]:
    issues: list[str] = []
    with Image.open(baseline_path) as baseline_image, Image.open(actual_path) as actual_image:
        base_rgb = baseline_image.convert("RGB")
        act_rgb = actual_image.convert("RGB")
        if base_rgb.size != act_rgb.size:
            return [
                (
                    f"{actual_path.name}: slide dimensions changed "
                    f"{base_rgb.size} -> {act_rgb.size}"
                )
            ]

        actual_hash = average_hash_hex(act_rgb)
        if hamming_hex(expected_hash, actual_hash) > MAX_AHASH_HAMMING:
            issues.append(
                f"{actual_path.name}: layout hash drift "
                f"(Hamming {hamming_hex(expected_hash, actual_hash)} > {MAX_AHASH_HAMMING})"
            )

        ratio = _diff_pixel_ratio(base_rgb, act_rgb)
        if ratio > max_pixel_diff_ratio:
            issues.append(
                f"{actual_path.name}: pixel diff {ratio:.1%} exceeds {max_pixel_diff_ratio:.1%}"
            )

        for edge in ("bottom", "right"):
            base_margin = _margin_ink_ratio(base_rgb, edge=edge, margin_ratio=MARGIN_OVERFLOW_RATIO)
            act_margin = _margin_ink_ratio(act_rgb, edge=edge, margin_ratio=MARGIN_OVERFLOW_RATIO)
            if act_margin - base_margin > MARGIN_OVERFLOW_DELTA:
                issues.append(
                    f"{actual_path.name}: possible {edge} margin overflow "
                    f"({act_margin:.1%} vs baseline {base_margin:.1%})"
                )
    return issues


def compare_structure(
    baseline: BaselineManifest,
    *,
    slides: list[SlideSpec],
    preview_paths: list[Path],
) -> list[str]:
    issues: list[str] = []
    if len(slides) != baseline.slide_count:
        issues.append(f"slide count changed: expected {baseline.slide_count}, got {len(slides)}")
    if len(preview_paths) != baseline.preview_count:
        issues.append(
            f"preview count changed: expected {baseline.preview_count}, got {len(preview_paths)}"
        )

    actual_snapshots = _slide_snapshots(slides)
    for expected, actual in zip(baseline.slides, actual_snapshots, strict=False):
        if not actual.title:
            issues.append(f"slide {actual.index}: missing title")
        if expected.title and actual.title != expected.title:
            issues.append(
                f"slide {actual.index}: title changed {expected.title!r} -> {actual.title!r}"
            )
        if expected.slide_type != actual.slide_type:
            issues.append(
                f"slide {actual.index}: slide_type changed "
                f"{expected.slide_type} -> {actual.slide_type}"
            )
    return issues


def compare_to_baseline(
    baseline: BaselineManifest,
    *,
    slides: list[SlideSpec],
    preview_paths: list[Path],
) -> list[str]:
    issues = compare_structure(baseline, slides=slides, preview_paths=preview_paths)
    if issues:
        return issues

    case_dir = baseline_dir(baseline.case_id)
    for preview_meta, actual_path in zip(baseline.previews, preview_paths, strict=True):
        baseline_path = case_dir / preview_meta.file
        if not baseline_path.exists():
            issues.append(f"missing baseline image: {preview_meta.file}")
            continue
        issues.extend(
            compare_preview_image(
                baseline_path,
                actual_path,
                expected_hash=preview_meta.average_hash,
            )
        )
    return issues
