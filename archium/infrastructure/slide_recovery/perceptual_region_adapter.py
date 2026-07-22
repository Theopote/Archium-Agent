"""Perceptual region analysis — real OCR + VLM for raster page inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.domain.slide_recovery import RecoveredPageRegion, SlideRecoveryPageKind
from archium.domain.visual.render_scene import ImageNode, RenderScene
from archium.infrastructure.slide_recovery.ocr_region_detector import (
    OcrDetectionResult,
    detect_text_regions,
)
from archium.infrastructure.slide_recovery.scene_region_adapter import classify_page_kind
from archium.infrastructure.slide_recovery.vlm_region_analyzer import (
    VlmAnalysisResult,
    VlmRegionAnalyzer,
)

_OVERLAP_IOU_THRESHOLD = 0.45


@dataclass(frozen=True)
class PerceptualAnalysisResult:
    regions: list[RecoveredPageRegion]
    page_kind: SlideRecoveryPageKind
    ocr_engine: str | None
    vlm_source: str | None
    ocr_char_count: int


def is_raster_proxy_scene(scene: RenderScene) -> bool:
    """True when the scene is a single full-page raster with no structural nodes."""
    if len(scene.nodes) != 1:
        return False
    node = scene.nodes[0]
    return isinstance(node, ImageNode) and node.semantic_role in {"source_page", ""}


def resolve_page_image_path(
    scene: RenderScene,
    explicit_path: Path | str | None = None,
) -> Path | None:
    if explicit_path is not None:
        path = Path(explicit_path)
        return path if path.is_file() else None
    for node in scene.nodes:
        if not isinstance(node, ImageNode):
            continue
        uri = (node.storage_uri or "").strip()
        if uri.startswith("file://"):
            path = Path(uri[7:])
            if path.is_file():
                return path
        elif uri and Path(uri).is_file():
            return Path(uri)
    return None


def regions_from_page_image(
    scene: RenderScene,
    image_path: Path | str,
    *,
    page_kind: SlideRecoveryPageKind | None = None,
    vlm_analyzer: VlmRegionAnalyzer | None = None,
    ocr_enabled: bool = True,
) -> PerceptualAnalysisResult:
    """Analyze a raster page via OCR text detection + VLM/heuristic visual regions."""
    path = Path(image_path)
    storage_uri = _primary_image_uri(scene)
    ocr_result = (
        detect_text_regions(
            path,
            page_width=scene.page_width,
            page_height=scene.page_height,
        )
        if ocr_enabled
        else OcrDetectionResult(regions=[], engine=None, char_count=0)
    )

    analyzer = vlm_analyzer or VlmRegionAnalyzer()
    vlm_result = analyzer.analyze(
        path,
        page_width=scene.page_width,
        page_height=scene.page_height,
        storage_uri=storage_uri,
    )

    visual_regions = [
        region
        for region in vlm_result.regions
        if not _overlaps_any_text(region, ocr_result.regions)
    ]
    regions = visual_regions + ocr_result.regions
    resolved_kind = (
        page_kind
        or vlm_result.page_kind
        or classify_page_kind(scene)
        or _classify_from_regions(regions)
    )
    return PerceptualAnalysisResult(
        regions=regions,
        page_kind=resolved_kind,
        ocr_engine=ocr_result.engine,
        vlm_source=vlm_result.source,
        ocr_char_count=ocr_result.char_count,
    )


def _primary_image_uri(scene: RenderScene) -> str | None:
    for node in scene.nodes:
        if isinstance(node, ImageNode) and node.storage_uri:
            return node.storage_uri
    return None


def _classify_from_regions(regions: list[RecoveredPageRegion]) -> SlideRecoveryPageKind:
    text_count = sum(1 for region in regions if region.region_type == "text")
    drawing_count = sum(1 for region in regions if region.region_type == "drawing")
    image_count = sum(1 for region in regions if region.region_type == "image")
    table_count = sum(1 for region in regions if region.region_type == "table")
    if drawing_count >= 1:
        return SlideRecoveryPageKind.DRAWING_DOMINANT
    if table_count >= 1:
        return SlideRecoveryPageKind.TABLE
    if image_count >= 1 and text_count <= 2:
        return SlideRecoveryPageKind.PHOTO
    if image_count >= 1 and text_count >= 2:
        return SlideRecoveryPageKind.IMAGE_TEXT
    if text_count <= 2:
        return SlideRecoveryPageKind.TITLE
    return SlideRecoveryPageKind.IMAGE_TEXT


def _overlaps_any_text(
    region: RecoveredPageRegion,
    text_regions: list[RecoveredPageRegion],
) -> bool:
    if region.region_type == "text":
        return True
    return any(_iou(region.bbox, text.bbox) >= _OVERLAP_IOU_THRESHOLD for text in text_regions)


def _iou(a: object, b: object) -> float:
    ax1, ay1 = a.x, a.y  # type: ignore[attr-defined]
    ax2, ay2 = ax1 + a.width, ay1 + a.height  # type: ignore[attr-defined]
    bx1, by1 = b.x, b.y  # type: ignore[attr-defined]
    bx2, by2 = bx1 + b.width, by1 + b.height  # type: ignore[attr-defined]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0
