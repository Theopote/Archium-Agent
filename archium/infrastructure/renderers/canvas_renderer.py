"""Canvas renderer for Studio — RenderScene as the interactive visual source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.domain.visual.render_scene import RenderNode, RenderScene
from archium.infrastructure.renderers.png_renderer import PngRenderer


@dataclass(frozen=True)
class CanvasNodeBounds:
    """Layout-space bounds for one RenderScene node (Studio overlay / hit testing)."""

    node_id: str
    source_layout_element_id: str | None
    x: float
    y: float
    width: float
    height: float
    z_index: int
    locked: bool
    node_type: str
    semantic_role: str


class CanvasRenderer:
    """Render RenderScene for Studio canvas (PNG backdrop + node bounds).

    Phase 5 uses PngRenderer as the pixel backend so Studio, HTML, and PNG
    share one scene. Interactive hit boxes come from scene node geometry.
    """

    def __init__(self, png_renderer: PngRenderer | None = None) -> None:
        self._png = png_renderer or PngRenderer()

    def render_preview(self, scene: RenderScene, output_path: Path) -> Path:
        """Write a scene_preview-compatible PNG for the Studio canvas backdrop."""
        return self._png.render(scene, output_path)

    def node_bounds(self, scene: RenderScene) -> list[CanvasNodeBounds]:
        """Return sorted node bounds for selection overlays."""
        return [
            self._bounds_for_node(node)
            for node in scene.sorted_nodes()
            if node.visible
        ]

    def _bounds_for_node(self, node: RenderNode) -> CanvasNodeBounds:
        return CanvasNodeBounds(
            node_id=node.id,
            source_layout_element_id=node.source_layout_element_id,
            x=node.x,
            y=node.y,
            width=node.width,
            height=node.height,
            z_index=node.z_index,
            locked=node.locked,
            node_type=node.node_type,
            semantic_role=node.semantic_role,
        )
