"""Slide recovery infrastructure adapters."""

from archium.infrastructure.slide_recovery.scene_region_adapter import (
    build_render_scene_from_regions,
    classify_page_kind,
    partition_regions,
    regions_from_render_scene,
)

__all__ = [
    "build_render_scene_from_regions",
    "classify_page_kind",
    "partition_regions",
    "regions_from_render_scene",
]
