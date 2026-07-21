"""Increase drawing readability on RenderScene by enlarging drawing nodes."""

from __future__ import annotations

from dataclasses import dataclass

from archium.application.slide_repair_policy import smart_shorten_text
from archium.domain.visual.render_scene import DrawingNode, RenderScene, TextNode
from archium.domain.visual.studio_command import IncreaseDrawingReadabilityCommand, ScenePatchAction

_PAGE_MARGIN_IN = 0.4
_TITLE_GAP_IN = 0.12
_BODY_GAP_IN = 0.1
_MIN_BODY_TEXT_CHARS = 12
_TITLE_ROLES = frozenset({"title", "heading", "central_claim"})


@dataclass(frozen=True)
class DrawingReadabilityResult:
    scene: RenderScene
    actions: tuple[ScenePatchAction, ...]
    area_ratio_before: float
    area_ratio_after: float


def node_area_ratio(node: DrawingNode, scene: RenderScene) -> float:
    page_area = scene.page_width * scene.page_height
    if page_area <= 0:
        return 0.0
    return (node.width * node.height) / page_area


def increase_drawing_readability(
    scene: RenderScene,
    command: IncreaseDrawingReadabilityCommand,
) -> DrawingReadabilityResult:
    patched = scene.model_copy(deep=True)
    drawing = patched.node_by_id(command.node_id)
    if not isinstance(drawing, DrawingNode):
        raise ValueError(f"node `{command.node_id}` is not a drawing node")

    before_ratio = node_area_ratio(drawing, patched)
    if before_ratio + 1e-6 >= command.target_min_area_ratio:
        return DrawingReadabilityResult(
            scene=patched,
            actions=(),
            area_ratio_before=before_ratio,
            area_ratio_after=before_ratio,
        )

    actions: list[ScenePatchAction] = []
    before_geometry = _geometry_token(drawing)

    _apply_drawing_policies(drawing, command)
    new_box = _compute_target_box(drawing, patched, command.target_min_area_ratio)
    drawing.x = new_box[0]
    drawing.y = new_box[1]
    drawing.width = new_box[2]
    drawing.height = new_box[3]

    actions.append(
        ScenePatchAction(
            scene_id=scene.slide_id,
            node_id=drawing.id,
            action_type="enlarge_drawing",
            property_name="geometry",
            before_value=before_geometry,
            after_value=_geometry_token(drawing),
            reason=(
                f"expanded drawing to {node_area_ratio(drawing, patched) * 100:.0f}% "
                f"of page area"
            ),
        )
    )

    if command.allow_reduce_body_text:
        actions.extend(
            _compress_overlapping_body_text(
                patched,
                drawing,
                scene_id=scene.slide_id,
            )
        )
        actions.extend(
            _relocate_overlapping_nodes(
                patched,
                drawing,
                scene_id=scene.slide_id,
            )
        )

    after_ratio = node_area_ratio(drawing, patched)
    return DrawingReadabilityResult(
        scene=patched,
        actions=tuple(actions),
        area_ratio_before=before_ratio,
        area_ratio_after=after_ratio,
    )


def _apply_drawing_policies(
    drawing: DrawingNode,
    command: IncreaseDrawingReadabilityCommand,
) -> None:
    drawing.fit_mode = "contain"
    if command.forbid_cover_crop:
        drawing.crop_allowed = False
    drawing.preserve_aspect_ratio = command.preserve_aspect_ratio
    drawing.preserve_annotations = command.preserve_annotations


def _compute_target_box(
    drawing: DrawingNode,
    scene: RenderScene,
    target_min_area_ratio: float,
) -> tuple[float, float, float, float]:
    page_w = scene.page_width
    page_h = scene.page_height
    page_area = page_w * page_h
    target_area = target_min_area_ratio * page_area

    top = _PAGE_MARGIN_IN
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.semantic_role in _TITLE_ROLES or node.id in {"title", "heading"}:
            top = max(top, node.y + node.height + _TITLE_GAP_IN)

    available_x = _PAGE_MARGIN_IN
    available_y = top
    available_w = max(0.5, page_w - 2 * _PAGE_MARGIN_IN)
    available_h = max(0.5, page_h - available_y - _PAGE_MARGIN_IN)

    aspect = drawing.width / max(drawing.height, 1e-6)
    width_from_area = (target_area * aspect) ** 0.5
    height_from_area = width_from_area / aspect

    new_w = min(available_w, max(drawing.width, width_from_area))
    new_h = min(available_h, max(drawing.height, height_from_area))
    if new_w / max(new_h, 1e-6) > aspect:
        new_w = new_h * aspect
    else:
        new_h = new_w / aspect

    if new_w * new_h + 1e-6 < target_area:
        fill_w = available_w
        fill_h = available_h
        if fill_w / max(fill_h, 1e-6) > aspect:
            fill_w = fill_h * aspect
        else:
            fill_h = fill_w / aspect
        new_w, new_h = fill_w, fill_h

    new_x = available_x + max(0.0, (available_w - new_w) / 2)
    new_y = available_y + max(0.0, (available_h - new_h) / 2)
    return new_x, new_y, new_w, new_h


def _compress_overlapping_body_text(
    scene: RenderScene,
    drawing: DrawingNode,
    *,
    scene_id,
) -> list[ScenePatchAction]:
    actions: list[ScenePatchAction] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        if node.id == drawing.id:
            continue
        if node.semantic_role in _TITLE_ROLES or node.id in {"title", "heading"}:
            continue
        if not _rects_overlap(node, drawing):
            continue
        if node.locked or "content" in node.lock_scopes or "all" in node.lock_scopes:
            continue
        limit = max(_MIN_BODY_TEXT_CHARS, len(node.text or "") // 2)
        shortened, applied, reason = smart_shorten_text(node.text or "", limit)
        if not applied or shortened == node.text:
            continue
        before = node.text
        node.text = shortened
        if node.paragraphs:
            node.paragraphs[0].text = shortened
        actions.append(
            ScenePatchAction(
                scene_id=scene_id,
                node_id=node.id,
                action_type="shorten_text",
                property_name="text",
                before_value=before,
                after_value=shortened,
                reason=reason or "compress body text for drawing readability",
            )
        )
    return actions


def _relocate_overlapping_nodes(
    scene: RenderScene,
    drawing: DrawingNode,
    *,
    scene_id,
) -> list[ScenePatchAction]:
    actions: list[ScenePatchAction] = []
    anchor_y = drawing.y + drawing.height + _BODY_GAP_IN
    for node in sorted(scene.nodes, key=lambda item: (item.y, item.x)):
        if node.id == drawing.id:
            continue
        if node.locked or "position" in node.lock_scopes or "all" in node.lock_scopes:
            continue
        if not _rects_overlap(node, drawing):
            continue
        before_y = node.y
        target_y = max(anchor_y, before_y)
        if target_y + node.height > scene.page_height - _PAGE_MARGIN_IN:
            target_y = max(
                drawing.y + drawing.height + _BODY_GAP_IN,
                scene.page_height - _PAGE_MARGIN_IN - node.height,
            )
        if abs(target_y - before_y) < 1e-3:
            continue
        node.y = target_y
        anchor_y = max(anchor_y, node.y + node.height + _BODY_GAP_IN)
        actions.append(
            ScenePatchAction(
                scene_id=scene_id,
                node_id=node.id,
                action_type="relocate_node",
                property_name="y",
                before_value=str(before_y),
                after_value=str(target_y),
                reason="move supporting content below enlarged drawing",
            )
        )
    return actions


def _rects_overlap(
    first: DrawingNode | TextNode,
    second: DrawingNode,
    *,
    gap: float = 0.02,
) -> bool:
    return not (
        first.x + first.width + gap <= second.x
        or second.x + second.width + gap <= first.x
        or first.y + first.height + gap <= second.y
        or second.y + second.height + gap <= first.y
    )


def _geometry_token(node: DrawingNode) -> str:
    return f"{node.x:.4f},{node.y:.4f},{node.width:.4f},{node.height:.4f}"


def parse_geometry_token(token: str) -> tuple[float, float, float, float]:
    parts = [float(part) for part in token.split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid geometry token: {token}")
    return parts[0], parts[1], parts[2], parts[3]
