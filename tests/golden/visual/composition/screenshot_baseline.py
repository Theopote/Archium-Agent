"""LayoutPlan PPTX screenshot baseline helpers (LibreOffice + pdftoppm)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from archium.infrastructure.renderers.pptx_screenshot import (
    export_pptx_slide_pngs,
    screenshot_tools_available,
)
from PIL import Image
from tests.golden.visual.baseline import average_hash_hex, compare_preview_image
from tests.golden.visual.composition.artifacts import maybe_export_pptx
from tests.golden.visual.composition.case_builders import (
    COMPOSITION_CASE_IDS,
    SCREENSHOT_CASE_IDS,
    CompositionCaseResult,
)

UPDATE_ENV = "UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS"
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "layout_family": self.layout_family,
            "layout_variant": self.layout_variant,
            "screenshot": asdict(self.screenshot),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PptxScreenshotManifest:
        screenshot = payload.get("screenshot") or {}
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
        )


def screenshot_baseline_path(case_dir: Path) -> Path:
    return case_dir / PPTX_SCREENSHOT_NAME


def manifest_path(case_dir: Path) -> Path:
    return case_dir / MANIFEST_NAME


def load_screenshot_manifest(case_dir: Path) -> PptxScreenshotManifest:
    path = manifest_path(case_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PptxScreenshotManifest.from_dict(payload)


def save_screenshot_baseline(
    case_dir: Path,
    *,
    case: CompositionCaseResult,
    screenshot_path: Path,
) -> Path:
    case_dir.mkdir(parents=True, exist_ok=True)
    target = screenshot_baseline_path(case_dir)
    target.write_bytes(screenshot_path.read_bytes())
    with Image.open(screenshot_path) as image:
        width, height = image.size
        image_hash = average_hash_hex(image.convert("RGB"))
    manifest = PptxScreenshotManifest(
        case_id=case.case_id,
        layout_family=case.plan.layout_family.value,
        layout_variant=case.plan.layout_variant,
        screenshot=PptxScreenshotSnapshot(
            file=PPTX_SCREENSHOT_NAME,
            width=width,
            height=height,
            average_hash=image_hash,
        ),
    )
    manifest_path(case_dir).write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


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
    issues = compare_preview_image(
        baseline_path,
        actual_path,
        expected_hash=manifest.screenshot.average_hash,
    )
    with Image.open(actual_path) as actual_image:
        width, height = actual_image.size
    if (width, height) != (manifest.screenshot.width, manifest.screenshot.height):
        issues.append(
            f"{actual_path.name}: screenshot dimensions changed "
            f"{manifest.screenshot.width}x{manifest.screenshot.height} -> {width}x{height}"
        )
    return issues


def update_mode_enabled() -> bool:
    return os.environ.get(UPDATE_ENV) == "1"


__all__ = [
    "COMPOSITION_CASE_IDS",
    "MANIFEST_NAME",
    "PPTX_SCREENSHOT_NAME",
    "SCREENSHOT_CASE_IDS",
    "UPDATE_ENV",
    "compare_screenshot_to_baseline",
    "load_screenshot_manifest",
    "manifest_path",
    "render_case_pptx",
    "render_case_pptx_screenshot",
    "save_screenshot_baseline",
    "screenshot_baseline_path",
    "screenshot_tools_available",
    "update_mode_enabled",
]
