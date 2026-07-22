"""Compile ElementEditIntent into StudioCommand plans."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.visual.studio_nl_command_planner import StudioCommandPlan
from archium.domain.visual.element_edit_intent import ElementEditIntent
from archium.domain.visual.partial_edit_preservation import PARTIAL_EDIT_INTERACTION_RULE
from archium.domain.visual.render_scene import DrawingNode, ImageNode, RenderNode, RenderScene, TextNode
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    IncreaseDrawingReadabilityCommand,
    MoveNodeCommand,
    NodeAlignment,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    StudioCommand,
    UpdateNodeStyleCommand,
)

_PAGE_MARGIN = 0.5


class ElementEditIntentCompiler:
    """Map a structured ElementEditIntent onto concrete StudioCommands."""

    def compile(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> StudioCommandPlan:
        node = scene.node_by_id(bound_node_id)
        if node is None:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason=f"绑定节点不存在：`{bound_node_id}`",
            )

        try:
            commands = self._compile_commands(
                intent,
                scene=scene,
                node=node,
                bound_node_id=bound_node_id,
                presentation_id=presentation_id,
                slide_id=slide_id,
            )
        except _CompileError as exc:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason=str(exc),
                confidence=intent.confidence,
            )

        if not commands:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason=f"无法将意图 `{intent.operation}` 编译为命令。",
                confidence=intent.confidence,
            )

        reasons = (
            PARTIAL_EDIT_INTERACTION_RULE,
            intent.rationale or f"element intent:{intent.operation}",
            *(command.expected_effect for command in commands if command.expected_effect),
        )
        return StudioCommandPlan(
            commands=tuple(commands),
            reasons=reasons,
            confidence=intent.confidence,
        )

    def _compile_commands(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        node: RenderNode,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> list[StudioCommand]:
        op = intent.operation
        if op == "move":
            return [
                self._move(
                    intent,
                    node=node,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "resize":
            return [
                self._resize(
                    intent,
                    scene=scene,
                    node=node,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "align":
            return [
                self._align(
                    intent,
                    scene=scene,
                    node=node,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "distribute":
            return [
                self._distribute(
                    intent,
                    scene=scene,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "rewrite_text":
            return [
                self._rewrite_text(
                    intent,
                    node=node,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "replace_asset":
            return [
                self._replace_asset(
                    intent,
                    node=node,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "change_style":
            return [
                self._change_style(
                    intent,
                    bound_node_id=bound_node_id,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                )
            ]
        if op == "visibility":
            visible = False if intent.visible is None else intent.visible
            return [
                SetNodeVisibilityCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    visible=visible,
                    reason="element intent: visibility",
                    expected_effect=("显示" if visible else "隐藏") + f" `{bound_node_id}`",
                )
            ]
        if op == "lock":
            locked = True if intent.locked is None else intent.locked
            return [
                SetNodeLockCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    locked=locked,
                    reason="element intent: lock",
                    expected_effect=("锁定" if locked else "解锁") + f" `{bound_node_id}`",
                )
            ]
        if op == "reorder":
            direction = (intent.direction or "front").lower()
            if direction not in {"front", "back", "forward", "backward"}:
                raise _CompileError(f"不支持的层级方向：`{direction}`")
            return [
                ReorderNodeCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    direction=direction,  # type: ignore[arg-type]
                    reason="element intent: reorder",
                    expected_effect=f"调整 `{bound_node_id}` 层级 → {direction}",
                )
            ]
        raise _CompileError(f"未实现的操作：`{op}`")

    def _move(
        self,
        intent: ElementEditIntent,
        *,
        node: RenderNode,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> MoveNodeCommand:
        direction = (intent.direction or "").lower()
        amount = intent.amount if intent.amount is not None else 0.25
        x, y = node.x, node.y
        if direction == "left":
            x -= amount
        elif direction == "right":
            x += amount
        elif direction == "up":
            y -= amount
        elif direction == "down":
            y += amount
        else:
            raise _CompileError("move 需要 direction=left|right|up|down")
        return MoveNodeCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=node.id,
            target_node_ids=[node.id],
            x=x,
            y=y,
            reason="element intent: move",
            expected_effect=f"将 `{node.id}` 向{direction}移动 {amount:g}in",
        )

    def _resize(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        node: RenderNode,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> StudioCommand:
        if intent.match_dimension:
            return self._match_size(
                intent,
                scene=scene,
                node=node,
                presentation_id=presentation_id,
                slide_id=slide_id,
            )

        direction = (intent.direction or "out").lower()
        if direction in {"in", "down", "smaller"} or (intent.amount is not None and intent.amount < 1.0):
            scale = intent.amount if intent.amount is not None else 0.85
        else:
            scale = intent.amount if intent.amount is not None else 1.15

        if isinstance(node, DrawingNode) or getattr(node, "node_type", "") == "drawing":
            if scale >= 1.0:
                return IncreaseDrawingReadabilityCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    reason="element intent: enlarge drawing",
                    expected_effect=f"扩大图纸 `{bound_node_id}`",
                )

        new_width = max(0.05, node.width * scale)
        new_height = max(0.05, node.height * scale)
        center_x = node.x + node.width / 2.0
        center_y = node.y + node.height / 2.0
        return ResizeNodeCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=bound_node_id,
            target_node_ids=[bound_node_id],
            x=center_x - new_width / 2.0,
            y=center_y - new_height / 2.0,
            width=new_width,
            height=new_height,
            preserve_aspect_ratio=True,
            reason="element intent: resize",
            expected_effect=f"缩放 `{bound_node_id}` ×{scale:g}",
        )

    def _match_size(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        node: RenderNode,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> ResizeNodeCommand:
        if not intent.reference_node_ids:
            raise _CompileError("等宽/等高需要 reference_node_ids")
        ref = scene.node_by_id(intent.reference_node_ids[0])
        if ref is None:
            raise _CompileError(f"参考节点不存在：`{intent.reference_node_ids[0]}`")
        width, height = node.width, node.height
        dim = intent.match_dimension or "width"
        if dim in {"width", "both"}:
            width = ref.width
        if dim in {"height", "both"}:
            height = ref.height
        return ResizeNodeCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=node.id,
            target_node_ids=[node.id],
            x=node.x,
            y=node.y,
            width=max(0.05, width),
            height=max(0.05, height),
            preserve_aspect_ratio=False,
            reason="element intent: match size",
            expected_effect=f"将 `{node.id}` 与 `{ref.id}` {dim} 对齐",
        )

    def _align(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        node: RenderNode,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> StudioCommand:
        alignment = _normalize_alignment(intent.direction)
        reference_id = intent.reference_node_ids[0] if intent.reference_node_ids else None
        if reference_id is None and alignment == "left":
            reference_id = _nearest_left_sibling_id(scene, bound_node_id)
        if reference_id is None and alignment == "right":
            reference_id = _nearest_right_sibling_id(scene, bound_node_id)

        if reference_id is not None:
            return AlignNodesCommand(
                presentation_id=presentation_id,
                slide_id=slide_id,
                node_ids=[bound_node_id, reference_id],
                target_node_ids=[bound_node_id],
                alignment=alignment,
                reference_node_id=reference_id,
                reason="element intent: align",
                expected_effect=f"将 `{bound_node_id}` {alignment} 对齐到 `{reference_id}`",
            )

        # Page-edge / page-center fallbacks for single-node align.
        x, y = node.x, node.y
        if alignment == "left":
            x = _PAGE_MARGIN
        elif alignment == "right":
            x = max(_PAGE_MARGIN, scene.page_width - node.width - _PAGE_MARGIN)
        elif alignment == "top":
            y = _PAGE_MARGIN
        elif alignment == "bottom":
            y = max(_PAGE_MARGIN, scene.page_height - node.height - _PAGE_MARGIN)
        elif alignment == "center":
            x = (scene.page_width - node.width) / 2.0
        elif alignment == "middle":
            y = (scene.page_height - node.height) / 2.0
        else:
            raise _CompileError(f"无法对齐：缺少参考节点且不支持 `{alignment}` 页面对齐")
        return MoveNodeCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=bound_node_id,
            target_node_ids=[bound_node_id],
            x=x,
            y=y,
            reason="element intent: align to page",
            expected_effect=f"将 `{bound_node_id}` {alignment} 对齐到页面",
        )

    def _distribute(
        self,
        intent: ElementEditIntent,
        *,
        scene: RenderScene,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> AlignNodesCommand:
        node_ids = [bound_node_id, *intent.reference_node_ids]
        # De-dupe preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for node_id in node_ids:
            if node_id in seen or scene.node_by_id(node_id) is None:
                continue
            seen.add(node_id)
            ordered.append(node_id)
        if len(ordered) < 3:
            raise _CompileError("distribute 至少需要 3 个节点（含绑定节点与 reference_node_ids）")
        direction = (intent.direction or "horizontal").lower()
        alignment: NodeAlignment = (
            "distribute_v" if direction in {"vertical", "v", "纵向"} else "distribute_h"
        )
        return AlignNodesCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_ids=ordered,
            target_node_ids=ordered,
            alignment=alignment,
            reason="element intent: distribute",
            expected_effect=f"分布节点 {', '.join(ordered)}",
        )

    def _rewrite_text(
        self,
        intent: ElementEditIntent,
        *,
        node: RenderNode,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> RewriteTextCommand:
        if not intent.text_value or not intent.text_value.strip():
            raise _CompileError("rewrite_text 需要 text_value")
        if not isinstance(node, TextNode):
            raise _CompileError(f"节点 `{bound_node_id}` 不是文本节点，无法改写文字")
        return RewriteTextCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=bound_node_id,
            target_node_ids=[bound_node_id],
            new_text=intent.text_value.strip(),
            reason="element intent: rewrite_text",
            expected_effect=f"改写 `{bound_node_id}` 文字",
        )

    def _replace_asset(
        self,
        intent: ElementEditIntent,
        *,
        node: RenderNode,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> StudioCommand:
        if not intent.asset_uri:
            raise _CompileError("replace_asset 需要 asset_uri（或通过结构化模型提供）")
        asset_id = intent.asset_id or uuid4()
        if isinstance(node, DrawingNode) or getattr(node, "node_type", "") == "drawing":
            return ReplaceDrawingCommand(
                presentation_id=presentation_id,
                slide_id=slide_id,
                node_id=bound_node_id,
                target_node_ids=[bound_node_id],
                asset_id=asset_id,
                storage_uri=intent.asset_uri,
                reason="element intent: replace_drawing",
                expected_effect=f"替换图纸 `{bound_node_id}`",
            )
        if not isinstance(node, ImageNode) and getattr(node, "node_type", "") != "image":
            raise _CompileError(f"节点 `{bound_node_id}` 不是图片/图纸，无法替换素材")
        return ReplaceAssetCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=bound_node_id,
            target_node_ids=[bound_node_id],
            asset_id=asset_id,
            storage_uri=intent.asset_uri,
            reason="element intent: replace_asset",
            expected_effect=f"替换图片 `{bound_node_id}`",
        )

    def _change_style(
        self,
        intent: ElementEditIntent,
        *,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> UpdateNodeStyleCommand:
        if intent.color_value is None and intent.font_size is None:
            raise _CompileError("change_style 需要 color_value 或 font_size")
        return UpdateNodeStyleCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=bound_node_id,
            target_node_ids=[bound_node_id],
            color=intent.color_value,
            font_size=intent.font_size,
            reason="element intent: change_style",
            expected_effect=f"更新 `{bound_node_id}` 样式",
        )


class _CompileError(ValueError):
    pass


def _normalize_alignment(direction: str | None) -> NodeAlignment:
    value = (direction or "left").lower()
    mapping = {
        "left": "left",
        "right": "right",
        "top": "top",
        "bottom": "bottom",
        "center": "center",
        "middle": "middle",
        "horizontal": "center",
        "vertical": "middle",
    }
    if value not in mapping:
        raise _CompileError(f"不支持的对齐方向：`{direction}`")
    return mapping[value]  # type: ignore[return-value]


def _nearest_left_sibling_id(scene: RenderScene, node_id: str) -> str | None:
    node = scene.node_by_id(node_id)
    if node is None:
        return None
    candidates: list[tuple[float, float, str]] = []
    for other in scene.nodes:
        if other.id == node_id or not other.visible:
            continue
        if other.x + other.width > node.x + 1e-6:
            continue
        vertical_gap = abs((other.y + other.height / 2.0) - (node.y + node.height / 2.0))
        horizontal_gap = node.x - (other.x + other.width)
        candidates.append((horizontal_gap, vertical_gap, other.id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _nearest_right_sibling_id(scene: RenderScene, node_id: str) -> str | None:
    node = scene.node_by_id(node_id)
    if node is None:
        return None
    candidates: list[tuple[float, float, str]] = []
    for other in scene.nodes:
        if other.id == node_id or not other.visible:
            continue
        if other.x < node.x + node.width - 1e-6:
            continue
        vertical_gap = abs((other.y + other.height / 2.0) - (node.y + node.height / 2.0))
        horizontal_gap = other.x - (node.x + node.width)
        candidates.append((horizontal_gap, vertical_gap, other.id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]
