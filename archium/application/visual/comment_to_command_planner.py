"""Plan StudioCommands from element-bound natural-language comments."""

from __future__ import annotations

from uuid import UUID

from archium.application.visual.partial_edit_preservation import command_target_node_ids
from archium.application.visual.studio_nl_command_planner import (
    StudioCommandPlan,
    StudioNLCommandPlanner,
)
from archium.config.settings import Settings, get_settings
from archium.domain.visual.element_comment import ElementComment
from archium.domain.visual.partial_edit_preservation import PARTIAL_EDIT_INTERACTION_RULE
from archium.domain.visual.render_scene import DrawingNode, RenderScene
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    IncreaseDrawingReadabilityCommand,
    MoveNodeCommand,
    ResizeNodeCommand,
    StudioCommand,
)

_ENLARGE_KEYWORDS: tuple[str, ...] = (
    "放大一点",
    "放大",
    "增大",
    "大一点",
    "enlarge",
    "scale up",
    "make bigger",
)

_ALIGN_LEFT_KEYWORDS: tuple[str, ...] = (
    "和左边对齐",
    "与左边对齐",
    "左对齐",
    "靠左",
    "align left",
    "align to the left",
)


class CommentToCommandPlanner:
    """Translate an ElementComment into Studio commands with a hard-bound target."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
        nl_planner: StudioNLCommandPlanner | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._nl_planner = nl_planner or StudioNLCommandPlanner(
            settings=self._settings,
            use_llm=use_llm,
        )

    def plan(
        self,
        comment: ElementComment,
        *,
        scene: RenderScene,
        presentation_id: UUID | None = None,
        slide_id: UUID | None = None,
    ) -> StudioCommandPlan:
        node = scene.node_by_id(comment.node_id)
        if node is None:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason=f"绑定节点不存在：`{comment.node_id}`",
            )

        presentation = presentation_id or comment.presentation_id
        slide = slide_id or comment.slide_id
        note = comment.note.strip()
        if not note:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason="请输入修改描述。",
            )

        geometry_plan = self._plan_geometry_keywords(
            note,
            scene=scene,
            bound_node_id=comment.node_id,
            presentation_id=presentation,
            slide_id=slide,
        )
        if geometry_plan is not None:
            return self._enforce_bound_targets(geometry_plan, comment.node_id)

        plan = self._nl_planner.plan_text(
            note,
            scene=scene,
            presentation_id=presentation,
            slide_id=slide,
            bound_node_id=comment.node_id,
        )
        return self._enforce_bound_targets(plan, comment.node_id)

    def _plan_geometry_keywords(
        self,
        text: str,
        *,
        scene: RenderScene,
        bound_node_id: str,
        presentation_id: UUID,
        slide_id: UUID,
    ) -> StudioCommandPlan | None:
        lowered = text.lower()
        wants_enlarge = any(keyword in lowered for keyword in _ENLARGE_KEYWORDS)
        wants_align_left = any(keyword in lowered for keyword in _ALIGN_LEFT_KEYWORDS)
        if not wants_enlarge and not wants_align_left:
            return None

        commands: list[StudioCommand] = []
        reasons: list[str] = []

        if wants_enlarge:
            node = scene.node_by_id(bound_node_id)
            assert node is not None
            if isinstance(node, DrawingNode) or getattr(node, "node_type", "") == "drawing":
                command: StudioCommand = IncreaseDrawingReadabilityCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    reason="element comment: enlarge drawing",
                    expected_effect=f"扩大图纸 `{bound_node_id}`",
                )
            else:
                scale = 1.15 if "一点" in text or "a bit" in lowered else 1.25
                new_width = node.width * scale
                new_height = node.height * scale
                center_x = node.x + node.width / 2.0
                center_y = node.y + node.height / 2.0
                command = ResizeNodeCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    x=center_x - new_width / 2.0,
                    y=center_y - new_height / 2.0,
                    width=new_width,
                    height=new_height,
                    preserve_aspect_ratio=True,
                    reason="element comment: enlarge node",
                    expected_effect=f"放大 `{bound_node_id}`",
                )
            commands.append(command)
            reasons.append(command.expected_effect)

        if wants_align_left:
            reference_id = _nearest_left_sibling_id(scene, bound_node_id)
            node = scene.node_by_id(bound_node_id)
            assert node is not None
            if reference_id is not None:
                align: StudioCommand = AlignNodesCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_ids=[bound_node_id, reference_id],
                    target_node_ids=[bound_node_id],
                    alignment="left",
                    reference_node_id=reference_id,
                    reason="element comment: align left",
                    expected_effect=f"将 `{bound_node_id}` 与左侧元素对齐",
                )
            else:
                # Single-node AlignNodesCommand is a no-op in scene_geometry.align_nodes;
                # fall back to an absolute move against the page left edge.
                margin = 0.5
                align = MoveNodeCommand(
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=bound_node_id,
                    target_node_ids=[bound_node_id],
                    x=margin,
                    y=node.y,
                    reason="element comment: align to page left",
                    expected_effect=f"将 `{bound_node_id}` 靠左对齐",
                )
            commands.append(align)
            reasons.append(align.expected_effect)

        if not commands:
            return None

        return StudioCommandPlan(
            commands=tuple(commands),
            reasons=(PARTIAL_EDIT_INTERACTION_RULE, *reasons),
            confidence=0.9,
        )

    @staticmethod
    def _enforce_bound_targets(
        plan: StudioCommandPlan,
        bound_node_id: str,
    ) -> StudioCommandPlan:
        if not plan.commands:
            return plan

        rewritten: list[StudioCommand] = []
        for command in plan.commands:
            updates: dict[str, object] = {}
            if hasattr(command, "node_id"):
                updates["node_id"] = bound_node_id
            if hasattr(command, "target_node_ids"):
                updates["target_node_ids"] = [bound_node_id]
            if hasattr(command, "node_ids") and getattr(command, "node_ids", None) is not None:
                existing = list(getattr(command, "node_ids") or [])
                # Keep secondary references (e.g. align reference) but force primary.
                others = [node_id for node_id in existing if node_id != bound_node_id]
                updates["node_ids"] = [bound_node_id, *others]
            rewritten.append(command.model_copy(update=updates) if updates else command)

        for command in rewritten:
            targets = command_target_node_ids(command)
            if bound_node_id not in targets:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason=(
                        f"无法将修改约束到绑定节点 `{bound_node_id}`，请换一种描述。"
                    ),
                )

        return StudioCommandPlan(
            commands=tuple(rewritten),
            reasons=plan.reasons,
            parsed_intent=plan.parsed_intent,
            confidence=plan.confidence,
            unsupported_reason=plan.unsupported_reason,
            uses_layout_fallback=plan.uses_layout_fallback,
        )


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
