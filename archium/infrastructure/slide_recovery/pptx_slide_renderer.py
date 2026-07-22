"""Rasterize a single PPTX slide to PNG for perceptual enhancement."""

from __future__ import annotations

from pathlib import Path

from archium.infrastructure.renderers.pptx_screenshot import export_pptx_slide_pngs
from archium.logging import get_logger

logger = get_logger(__name__, operation="slide_recovery_pptx_render")


def render_pptx_slide_png(
    pptx_path: Path | str,
    *,
    slide_index: int = 0,
    workspace_dir: Path | None,
) -> Path | None:
    """Return PNG path for one slide, or None when raster tools are unavailable."""
    source = Path(pptx_path)
    if not source.is_file():
        return None
    if workspace_dir is None:
        workspace_dir = source.parent / ".slide_recovery_previews"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    pngs = export_pptx_slide_pngs(source, workspace_dir)
    if not pngs:
        logger.info("PPTX slide preview unavailable for %s (index=%s)", source.name, slide_index)
        return None
    if slide_index < 0 or slide_index >= len(pngs):
        return None
    return pngs[slide_index]
