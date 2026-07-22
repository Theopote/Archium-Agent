"""Geometry helpers for Studio scene-level edits."""

from __future__ import annotations

from archium.domain.visual.render_scene import BaseRenderNode, RenderScene
from archium.domain.visual.studio_command import NodeAlignment


def geometry_token(node: BaseRenderNode) -> str:
    """Serialize node bounds for reversible ScenePatchAction values."""
    return f"{node.x},{node.y},{node.width},{node.height}"


def parse_geometry_token(token: str) -> tuple[float, float, float, float]:
    parts = [float(part) for part in token.split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid geometry token: {token}")
    return parts[0], parts[1], parts[2], parts[3]


def apply_geometry_token(node: BaseRenderNode, token: str) -> None:
    x, y, width, height = parse_geometry_token(token)
    node.x = x
    node.y = y
    node.width = width
    node.height = height


def align_nodes(
    nodes: list[BaseRenderNode],
    alignment: NodeAlignment,
    *,
    reference: BaseRenderNode | None = None,
) -> dict[str, str]:
    """Return node_id -> geometry_token for aligned positions."""
    if not nodes:
        return {}
    if len(nodes) == 1 and alignment not in {"distribute_h", "distribute_v"}:
        return {}

    ref = reference or _bounding_box(nodes)
    updates: dict[str, str] = {}

    if alignment == "left":
        target_x = ref.x
        for node in nodes:
            if abs(node.x - target_x) < 1e-6:
                continue
            node.x = target_x
            updates[node.id] = geometry_token(node)
    elif alignment == "center":
        ref_center = ref.x + ref.width / 2
        for node in nodes:
            next_x = ref_center - node.width / 2
            if abs(node.x - next_x) < 1e-6:
                continue
            node.x = next_x
            updates[node.id] = geometry_token(node)
    elif alignment == "right":
        target_right = ref.x + ref.width
        for node in nodes:
            next_x = target_right - node.width
            if abs(node.x - next_x) < 1e-6:
                continue
            node.x = next_x
            updates[node.id] = geometry_token(node)
    elif alignment == "top":
        target_y = ref.y
        for node in nodes:
            if abs(node.y - target_y) < 1e-6:
                continue
            node.y = target_y
            updates[node.id] = geometry_token(node)
    elif alignment == "middle":
        ref_middle = ref.y + ref.height / 2
        for node in nodes:
            next_y = ref_middle - node.height / 2
            if abs(node.y - next_y) < 1e-6:
                continue
            node.y = next_y
            updates[node.id] = geometry_token(node)
    elif alignment == "bottom":
        target_bottom = ref.y + ref.height
        for node in nodes:
            next_y = target_bottom - node.height
            if abs(node.y - next_y) < 1e-6:
                continue
            node.y = next_y
            updates[node.id] = geometry_token(node)
    elif alignment == "distribute_h":
        if len(nodes) < 3:
            return {}
        ordered = sorted(nodes, key=lambda item: item.x)
        left = ordered[0].x
        right = ordered[-1].x + ordered[-1].width
        total_width = sum(node.width for node in ordered)
        gap = (right - left - total_width) / (len(ordered) - 1)
        cursor = left
        for node in ordered:
            if abs(node.x - cursor) > 1e-6:
                node.x = cursor
                updates[node.id] = geometry_token(node)
            cursor += node.width + gap
    elif alignment == "distribute_v":
        if len(nodes) < 3:
            return {}
        ordered = sorted(nodes, key=lambda item: item.y)
        top = ordered[0].y
        bottom = ordered[-1].y + ordered[-1].height
        total_height = sum(node.height for node in ordered)
        gap = (bottom - top - total_height) / (len(ordered) - 1)
        cursor = top
        for node in ordered:
            if abs(node.y - cursor) > 1e-6:
                node.y = cursor
                updates[node.id] = geometry_token(node)
            cursor += node.height + gap
    return updates


def reorder_node_z_index(
    scene: RenderScene,
    node: BaseRenderNode,
    direction: str,
) -> int:
    """Return the next z-index for a node given a reorder direction."""
    visible_nodes = [item for item in scene.nodes if item.visible]
    z_values = sorted({item.z_index for item in visible_nodes})
    if not z_values:
        return node.z_index

    current = node.z_index
    if direction == "front":
        return max(z_values) + 1
    if direction == "back":
        return min(z_values) - 1
    if direction == "forward":
        higher = [value for value in z_values if value > current]
        return higher[0] if higher else current
    if direction == "backward":
        lower = [value for value in z_values if value < current]
        return lower[-1] if lower else current
    return current


class _Box:
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height


def page_box(page_width: float, page_height: float) -> _Box:
    """Return the full slide bounds as an alignment reference."""
    return _Box(0.0, 0.0, page_width, page_height)


def _bounding_box(nodes: list[BaseRenderNode]) -> _Box:
    left = min(node.x for node in nodes)
    top = min(node.y for node in nodes)
    right = max(node.x + node.width for node in nodes)
    bottom = max(node.y + node.height for node in nodes)
    return _Box(left, top, right - left, bottom - top)
