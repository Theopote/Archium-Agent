"""Slide recovery infrastructure adapters."""

from archium.infrastructure.slide_recovery.ocr_region_detector import (
    detect_text_regions,
    pytesseract_available,
)
from archium.infrastructure.slide_recovery.perceptual_region_adapter import (
    is_raster_proxy_scene,
    regions_from_page_image,
    resolve_page_image_path,
)
from archium.infrastructure.slide_recovery.scene_region_adapter import (
    build_render_scene_from_regions,
    classify_page_kind,
    partition_regions,
    regions_from_render_scene,
)
from archium.infrastructure.slide_recovery.pdf_page_renderer import (
    pymupdf_available,
    render_pdf_page_png,
)
from archium.infrastructure.slide_recovery.pptx_slide_renderer import render_pptx_slide_png
from archium.infrastructure.slide_recovery.structural_perceptual_merge import (
    merge_structural_and_perceptual,
)
from archium.infrastructure.slide_recovery.vlm_region_analyzer import VlmRegionAnalyzer

__all__ = [
    "VlmRegionAnalyzer",
    "build_render_scene_from_regions",
    "classify_page_kind",
    "detect_text_regions",
    "is_raster_proxy_scene",
    "merge_structural_and_perceptual",
    "partition_regions",
    "pymupdf_available",
    "pytesseract_available",
    "regions_from_page_image",
    "regions_from_render_scene",
    "render_pdf_page_png",
    "render_pptx_slide_png",
    "resolve_page_image_path",
]
