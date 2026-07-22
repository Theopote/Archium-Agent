"""Helpers to build region / selection comment bindings from Studio selection."""

from __future__ import annotations

from archium.domain.visual.render_scene import BaseRenderNode, RenderScene


def selection_region_bbox(
    scene: RenderScene,
    node_ids: list[str],
) -> dict[str, float] | None:
    """Axis-aligned page-inch bbox covering the given nodes."""
    nodes: list[BaseRenderNode] = []
    for node_id in node_ids:
        node = scene.node_by_id(node_id)
        if node is not None:
            nodes.append(node)
    if not nodes:
        return None
    left = min(node.x for node in nodes)
    top = min(node.y for node in nodes)
    right = max(node.x + node.width for node in nodes)
    bottom = max(node.y + node.height for node in nodes)
    return {
        "x": float(left),
        "y": float(top),
        "width": float(max(0.01, right - left)),
        "height": float(max(0.01, bottom - top)),
    }
