"""Build non-interactive canvas overlays for ElementComment anchors."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.domain.visual.element_comment import ElementComment, ElementCommentStatus
from archium.domain.visual.render_scene import RenderScene

_ACTIVE_STATUSES = {
    ElementCommentStatus.PENDING,
    ElementCommentStatus.PROPOSED,
    ElementCommentStatus.NEEDS_REBASE,
}

_SNAPSHOT_COMPARE_KEYS = (
    "x",
    "y",
    "width",
    "height",
    "text",
    "visible",
    "asset_id",
    "locked",
    "z_index",
)


def canvas_element_id_for_node(scene: RenderScene | None, node_id: str) -> str:
    """Map RenderScene node id → Layout element id used by the canvas."""
    if scene is None:
        return node_id
    node = scene.node_by_id(node_id)
    if node is None:
        return node_id
    layout_id = getattr(node, "source_layout_element_id", None)
    return str(layout_id) if layout_id else node_id


def comment_snapshot_diff(
    comment: ElementComment,
    *,
    scene: RenderScene | None,
) -> list[tuple[str, Any, Any]]:
    """Return ``(field, snapshot_value, live_value)`` rows that differ."""
    snapshot = dict(comment.node_snapshot_json or {})
    live: dict[str, Any] = {}
    if scene is not None:
        node = scene.node_by_id(comment.node_id)
        if node is not None:
            live = node.model_dump(mode="json")
    rows: list[tuple[str, Any, Any]] = []
    keys = list(_SNAPSHOT_COMPARE_KEYS)
    for key in keys:
        if key not in snapshot and key not in live:
            continue
        old = snapshot.get(key)
        new = live.get(key)
        if old != new:
            rows.append((key, old, new))
    return rows


def build_comment_canvas_anchors(
    comments: list[ElementComment],
    *,
    page_width: float,
    page_height: float,
    scene: RenderScene | None = None,
    focused_comment_id: UUID | None = None,
    focused_region_bbox: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Convert active comments + optional focus region into %-based overlays.

    Coordinates are page percentages (0–100), matching ``convert_elements_for_canvas``.
    """
    width = max(page_width, 0.01)
    height = max(page_height, 0.01)
    anchors: list[dict[str, Any]] = []

    for comment in comments:
        if comment.status not in _ACTIVE_STATUSES:
            continue
        focused = focused_comment_id is not None and comment.id == focused_comment_id
        element_id = comment.layout_element_id or canvas_element_id_for_node(
            scene, comment.node_id
        )

        if comment.region_bbox:
            box = comment.region_bbox
            anchors.append(
                {
                    "id": str(comment.id),
                    "nodeId": comment.node_id,
                    "elementId": element_id,
                    "status": comment.status.value,
                    "kind": "region",
                    "x": float(box.get("x", 0.0)) / width * 100.0,
                    "y": float(box.get("y", 0.0)) / height * 100.0,
                    "width": float(box.get("width", 0.0)) / width * 100.0,
                    "height": float(box.get("height", 0.0)) / height * 100.0,
                    "focused": focused,
                }
            )
            continue

        geom = _node_geometry(scene, comment.node_id, comment.node_snapshot_json)
        if geom is None:
            continue
        x, y, w, h = geom
        # Pin at top-right of node bbox (small marker, not a full box).
        pin_x = (x + w) / width * 100.0
        pin_y = y / height * 100.0
        anchors.append(
            {
                "id": str(comment.id),
                "nodeId": comment.node_id,
                "elementId": element_id,
                "status": comment.status.value,
                "kind": "node",
                "x": max(0.0, min(100.0, pin_x)),
                "y": max(0.0, min(100.0, pin_y)),
                "focused": focused,
            }
        )

    if focused_region_bbox and not any(
        a.get("focused") and a.get("kind") == "region" for a in anchors
    ):
        box = focused_region_bbox
        anchors.append(
            {
                "id": "focus-region",
                "nodeId": "",
                "elementId": "",
                "status": "pending",
                "kind": "region",
                "x": float(box.get("x", 0.0)) / width * 100.0,
                "y": float(box.get("y", 0.0)) / height * 100.0,
                "width": float(box.get("width", 0.0)) / width * 100.0,
                "height": float(box.get("height", 0.0)) / height * 100.0,
                "focused": True,
            }
        )

    return anchors


def _node_geometry(
    scene: RenderScene | None,
    node_id: str,
    snapshot: dict[str, Any] | None,
) -> tuple[float, float, float, float] | None:
    if scene is not None:
        node = scene.node_by_id(node_id)
        if node is not None:
            return (
                float(node.x),
                float(node.y),
                float(node.width),
                float(node.height),
            )
    if snapshot:
        try:
            return (
                float(snapshot["x"]),
                float(snapshot["y"]),
                float(snapshot["width"]),
                float(snapshot["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    return None
