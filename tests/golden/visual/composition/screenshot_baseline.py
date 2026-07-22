"""LayoutPlan PPTX screenshot baseline helpers (LibreOffice + pdftoppm)."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from archium.infrastructure.layout.font_manifest import (
    build_measurement_font_bundle,
    compare_font_manifest_binding,
)
from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from PIL import Image
from tests.golden.visual.baseline import average_hash_hex, compare_preview_image
from tests.golden.visual.composition.artifacts import maybe_export_pptx
from tests.golden.visual.composition.case_builders import (
    COMPOSITION_CASE_IDS,
    PPTX_VISUAL_REGRESSION_CASE_IDS,
    SCREENSHOT_CASE_IDS,
    CompositionCaseResult,
)
from tests.golden.visual.composition.visual_regression_tracks import (
    CANDIDATE_ENV,
    CANDIDATE_MANIFEST_NAME,
    CANDIDATE_SCREENSHOT_NAME,
    LEGACY_UPDATE_ENV,
)

UPDATE_ENV = LEGACY_UPDATE_ENV  # back-compat export
PPTX_SCREENSHOT_NAME = "pptx_screenshot.png"
MANIFEST_NAME = "pptx_screenshot_manifest.json"


@dataclass(frozen=True)
class PptxScreenshotSnapshot:
    file: str
    width: int
    height: int
    average_hash: str


@dataclass(frozen=True)
class PptxScreenshotManifest:
    case_id: str
    layout_family: str
    layout_variant: str
    screenshot: PptxScreenshotSnapshot
    font_manifest_hash: str | None = None
    font_platform: str | None = None
    measurement_engine: str | None = None
    fonts: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "layout_family": self.layout_family,
            "layout_variant": self.layout_variant,
            "screenshot": asdict(self.screenshot),
            "font_manifest_hash": self.font_manifest_hash,
            "font_platform": self.font_platform,
            "measurement_engine": self.measurement_engine,
            "fonts": list(self.fonts),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PptxScreenshotManifest:
        screenshot = payload.get("screenshot") or {}
        fonts_raw = payload.get("fonts") or []
        fonts = tuple(dict(item) for item in fonts_raw if isinstance(item, dict))
        return cls(
            case_id=str(payload["case_id"]),
            layout_family=str(payload["layout_family"]),
            layout_variant=str(payload["layout_variant"]),
            screenshot=PptxScreenshotSnapshot(
                file=str(screenshot["file"]),
                width=int(screenshot["width"]),
                height=int(screenshot["height"]),
                average_hash=str(screenshot["average_hash"]),
            ),
            font_manifest_hash=(
                None
                if payload.get("font_manifest_hash") in (None, "")
                else str(payload.get("font_manifest_hash"))
            ),
            font_platform=(
                None
                if payload.get("font_platform") in (None, "")
                else str(payload.get("font_platform"))
            ),
            measurement_engine=(
                None
                if payload.get("measurement_engine") in (None, "")
                else str(payload.get("measurement_engine"))
            ),
            fonts=fonts,
        )


def screenshot_baseline_path(case_dir: Path) -> Path:
    return case_dir / PPTX_SCREENSHOT_NAME


def manifest_path(case_dir: Path) -> Path:
    return case_dir / MANIFEST_NAME


def candidate_dir(case_dir: Path) -> Path:
    from tests.golden.visual.composition.visual_regression_tracks import CANDIDATE_DIRNAME

    return case_dir / CANDIDATE_DIRNAME


def candidate_screenshot_path(case_dir: Path) -> Path:
    return candidate_dir(case_dir) / CANDIDATE_SCREENSHOT_NAME


def candidate_manifest_path(case_dir: Path) -> Path:
    return candidate_dir(case_dir) / CANDIDATE_MANIFEST_NAME


def load_screenshot_manifest(case_dir: Path) -> PptxScreenshotManifest:
    path = manifest_path(case_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PptxScreenshotManifest.from_dict(payload)


def _write_screenshot_pair(
    *,
    png_target: Path,
    manifest_target: Path,
    case: CompositionCaseResult,
    screenshot_path: Path,
    screenshot_filename: str,
) -> Path:
    png_target.parent.mkdir(parents=True, exist_ok=True)
    png_target.write_bytes(screenshot_path.read_bytes())
    with Image.open(screenshot_path) as image:
        width, height = image.size
        image_hash = average_hash_hex(image.convert("RGB"))
    font_bundle = build_measurement_font_bundle()
    manifest = PptxScreenshotManifest(
        case_id=case.case_id,
        layout_family=case.plan.layout_family.value,
        layout_variant=case.plan.layout_variant,
        screenshot=PptxScreenshotSnapshot(
            file=screenshot_filename,
            width=width,
            height=height,
            average_hash=image_hash,
        ),
        font_manifest_hash=font_bundle.font_manifest_hash,
        font_platform=font_bundle.platform,
        measurement_engine=font_bundle.measurement_engine,
        fonts=tuple(font.to_dict() for font in font_bundle.fonts),
    )
    manifest_target.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return png_target


def save_screenshot_candidate(
    case_dir: Path,
    *,
    case: CompositionCaseResult,
    screenshot_path: Path,
) -> Path:
    """Write reviewable candidate images — does **not** touch committed baselines."""
    return _write_screenshot_pair(
        png_target=candidate_screenshot_path(case_dir),
        manifest_target=candidate_manifest_path(case_dir),
        case=case,
        screenshot_path=screenshot_path,
        screenshot_filename=CANDIDATE_SCREENSHOT_NAME,
    )


def save_screenshot_baseline(
    case_dir: Path,
    *,
    case: CompositionCaseResult,
    screenshot_path: Path,
) -> Path:
    """Write committed baseline — only call from approve-baseline after human review."""
    return _write_screenshot_pair(
        png_target=screenshot_baseline_path(case_dir),
        manifest_target=manifest_path(case_dir),
        case=case,
        screenshot_path=screenshot_path,
        screenshot_filename=PPTX_SCREENSHOT_NAME,
    )


def approve_candidate_baseline(case_dir: Path) -> Path:
    """Promote ``candidates/`` → committed baseline after human review."""
    candidate_png = candidate_screenshot_path(case_dir)
    candidate_manifest = candidate_manifest_path(case_dir)
    if not candidate_png.is_file() or not candidate_manifest.is_file():
        raise FileNotFoundError(
            f"Missing candidates for {case_dir.name}: "
            f"expected {candidate_png.name} and {candidate_manifest.name}"
        )
    target_png = screenshot_baseline_path(case_dir)
    target_manifest = manifest_path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_png, target_png)
    payload = json.loads(candidate_manifest.read_text(encoding="utf-8"))
    if isinstance(payload.get("screenshot"), dict):
        payload["screenshot"]["file"] = PPTX_SCREENSHOT_NAME
    # Ensure approve always binds fonts even for older candidates.
    if not payload.get("font_manifest_hash"):
        font_bundle = build_measurement_font_bundle()
        payload["font_manifest_hash"] = font_bundle.font_manifest_hash
        payload["font_platform"] = font_bundle.platform
        payload["measurement_engine"] = font_bundle.measurement_engine
        payload["fonts"] = [font.to_dict() for font in font_bundle.fonts]
    target_manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_png


def render_case_pptx(
    case: CompositionCaseResult,
    output_path: Path,
) -> Path | None:
    """Render a single-slide LayoutPlan deck via PptxGenJS."""
    return maybe_export_pptx(
        case.plan,
        case.design,
        output_path,
        title=case.title,
    )


def rasterize_pptx_first_slide(pptx_path: Path, output_dir: Path) -> Path | None:
    pngs = export_pptx_slide_pngs(pptx_path, output_dir)
    return pngs[0] if pngs else None


def render_case_pptx_screenshot(
    case: CompositionCaseResult,
    work_dir: Path,
) -> Path | None:
    """LayoutPlan → PPTX → PNG (requires Node + LibreOffice + pdftoppm)."""
    pptx_path = work_dir / "deck.pptx"
    rendered = render_case_pptx(case, pptx_path)
    if rendered is None:
        return None
    screenshot_dir = work_dir / "screenshots"
    return rasterize_pptx_first_slide(rendered, screenshot_dir)


def compare_screenshot_to_baseline(case_dir: Path, actual_path: Path) -> list[str]:
    baseline_path = screenshot_baseline_path(case_dir)
    if not baseline_path.is_file():
        return [f"Missing baseline screenshot: {baseline_path}"]
    if not manifest_path(case_dir).is_file():
        return [f"Missing screenshot manifest: {manifest_path(case_dir)}"]

    manifest = load_screenshot_manifest(case_dir)
    font_issues = compare_font_manifest_binding(
        baseline_hash=manifest.font_manifest_hash,
        baseline_platform=manifest.font_platform,
        baseline_fonts=list(manifest.fonts),
    )
    # Same-platform hash drift / missing hash fail before pixel noise.
    font_blocking = [
        issue
        for issue in font_issues
        if issue.startswith("Missing font_manifest_hash")
        or issue.startswith("font_manifest_hash mismatch")
    ]
    if font_blocking:
        return font_blocking

    issues = list(font_issues)
    issues.extend(
        compare_preview_image(
            baseline_path,
            actual_path,
            expected_hash=manifest.screenshot.average_hash,
        )
    )
    with Image.open(actual_path) as actual_image:
        width, height = actual_image.size
    if (width, height) != (manifest.screenshot.width, manifest.screenshot.height):
        issues.append(
            f"{actual_path.name}: screenshot dimensions changed "
            f"{manifest.screenshot.width}x{manifest.screenshot.height} -> {width}x{height}"
        )
    return issues


def candidate_mode_enabled() -> bool:
    return os.environ.get(CANDIDATE_ENV) == "1" or os.environ.get(LEGACY_UPDATE_ENV) == "1"


def update_mode_enabled() -> bool:
    """Deprecated alias — only enables candidate write, never silent baseline overwrite."""
    return candidate_mode_enabled()


__all__ = [
    "CANDIDATE_ENV",
    "COMPOSITION_CASE_IDS",
    "MANIFEST_NAME",
    "PPTX_SCREENSHOT_NAME",
    "PPTX_VISUAL_REGRESSION_CASE_IDS",
    "SCREENSHOT_CASE_IDS",
    "UPDATE_ENV",
    "approve_candidate_baseline",
    "candidate_mode_enabled",
    "compare_screenshot_to_baseline",
    "load_screenshot_manifest",
    "manifest_path",
    "render_case_pptx",
    "render_case_pptx_screenshot",
    "save_screenshot_baseline",
    "save_screenshot_candidate",
    "screenshot_baseline_path",
    "screenshot_tools_available",
    "update_mode_enabled",
]
