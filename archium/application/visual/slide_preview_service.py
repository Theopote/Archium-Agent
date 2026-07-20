"""Resolve slide preview images for Studio and visual UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.visual.layout import LayoutPlan
from archium.infrastructure.visual.layout_preview_renderer import render_layout_preview_png

PreviewKind = Literal["scene", "screenshot", "wireframe"]


@dataclass(frozen=True)
class SlidePreviewResolution:
    slide_index: int
    path: str | None
    kind: PreviewKind | None


def map_preview_pngs_by_order(render_paths: list[str]) -> dict[int, str]:
    """Map 0-based slide index → PNG path from workflow render artifacts."""
    previews = sorted(
        [
            path
            for path in render_paths
            if path.lower().endswith(".png")
            and (
                "slide_preview" in path.replace("\\", "/").lower()
                or Path(path).name.lower().startswith("slide_")
            )
        ],
        key=lambda value: Path(value).name,
    )
    return {index: path for index, path in enumerate(previews)}


def find_latest_slide_preview_dir(
    presentation_id: UUID,
    *,
    settings: Settings,
    preferred_output_dir: Path | str | None = None,
) -> Path | None:
    """Locate the newest on-disk ``slide_previews/`` folder for a presentation."""
    if preferred_output_dir is not None:
        preview_dir = Path(preferred_output_dir) / "slide_previews"
        if preview_dir.is_dir() and any(preview_dir.glob("slide_*.png")):
            return preview_dir

    base = settings.output_path / "visual-composition" / str(presentation_id)
    if not base.is_dir():
        return None

    candidates: list[Path] = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        preview_dir = run_dir / "slide_previews"
        if preview_dir.is_dir() and any(preview_dir.glob("slide_*.png")):
            candidates.append(preview_dir)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


class SlidePreviewService:
    """Resolve scene / screenshot / wireframe previews for slide navigation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def resolve_previews(
        self,
        *,
        presentation_id: UUID,
        layout_plans: list[LayoutPlan | None],
        existing_preview_by_index: dict[int, str | None] | None = None,
        render_paths: list[str] | None = None,
        workflow_output_dir: Path | str | None = None,
        scene_preview_by_index: dict[int, str | None] | None = None,
    ) -> list[SlidePreviewResolution]:
        """Return preview path + kind for each slide index.

        Priority (Phase 5): RenderScene preview → PPTX screenshot → LayoutPlan wireframe.
        """
        slide_count = len(layout_plans)
        screenshot_by_index = self._resolve_screenshot_paths(
            presentation_id,
            slide_count=slide_count,
            render_paths=list(render_paths or []),
            workflow_output_dir=workflow_output_dir,
        )
        existing = existing_preview_by_index or {}
        scene_by_index = scene_preview_by_index or {}
        resolutions: list[SlidePreviewResolution] = []

        for index, plan in enumerate(layout_plans):
            preview_path = existing.get(index)
            preview_kind: PreviewKind | None = None

            scene_path = scene_by_index.get(index)
            if scene_path and Path(scene_path).is_file():
                preview_path = scene_path
                preview_kind = "scene"
            else:
                screenshot_path = screenshot_by_index.get(index)
                if screenshot_path and Path(screenshot_path).is_file():
                    preview_path = screenshot_path
                    preview_kind = "screenshot"
                elif preview_path and Path(preview_path).is_file():
                    preview_kind = "screenshot"
                elif plan is not None:
                    wireframe_path = self._ensure_wireframe_preview(presentation_id, plan)
                    if wireframe_path is not None:
                        preview_path = str(wireframe_path)
                        preview_kind = "wireframe"

            resolutions.append(
                SlidePreviewResolution(
                    slide_index=index,
                    path=preview_path,
                    kind=preview_kind,
                )
            )
        return resolutions

    def _resolve_screenshot_paths(
        self,
        presentation_id: UUID,
        *,
        slide_count: int,
        render_paths: list[str],
        workflow_output_dir: Path | str | None,
    ) -> dict[int, str]:
        by_index = map_preview_pngs_by_order(render_paths)
        if len(by_index) >= slide_count:
            return by_index

        preview_dir = find_latest_slide_preview_dir(
            presentation_id,
            settings=self._settings,
            preferred_output_dir=workflow_output_dir,
        )
        if preview_dir is None:
            return by_index

        disk_paths = [str(path) for path in sorted(preview_dir.glob("slide_*.png"), key=lambda p: p.name)]
        merged_paths = list(render_paths)
        for path in disk_paths:
            if path not in merged_paths:
                merged_paths.append(path)
        return map_preview_pngs_by_order(merged_paths)

    def _ensure_wireframe_preview(
        self,
        presentation_id: UUID,
        plan: LayoutPlan,
    ) -> Path | None:
        cache_dir = self._settings.output_path / "studio-previews" / str(presentation_id)
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_path = cache_dir / f"{plan.id}.png"
        if output_path.is_file():
            return output_path
        try:
            return render_layout_preview_png(plan, output_path)
        except Exception:
            return None
