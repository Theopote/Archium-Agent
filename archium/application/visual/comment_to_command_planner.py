"""Plan StudioCommands from element-bound natural-language comments."""

from __future__ import annotations

from uuid import UUID

from archium.application.visual.element_edit_intent_compiler import ElementEditIntentCompiler
from archium.application.visual.element_edit_intent_parser import ElementEditIntentParser
from archium.application.visual.partial_edit_preservation import command_target_node_ids
from archium.application.visual.studio_nl_command_planner import (
    StudioCommandPlan,
    StudioNLCommandPlanner,
)
from archium.config.settings import Settings, get_settings
from archium.domain.visual.element_comment import ElementComment, ElementCommentScope
from archium.domain.visual.render_scene import RenderNode, RenderScene
from archium.domain.visual.studio_command import StudioCommand

# Multi-node intents that conflict with default NODE hard-binding.
_MULTI_NODE_SCOPE_HINTS: tuple[str, ...] = (
    "这三个",
    "这三张",
    "这几",
    "这几张",
    "大小一致",
    "同样大小",
    "统一大小",
    "三列",
    "重新排",
    "排成",
    "并排成",
    "equal size",
    "same size",
    "three columns",
    "reflow",
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
    """Translate an ElementComment into Studio commands with scope-aware targets.

    Pipeline:
    1. Scope gate for multi-node notes under ``NODE``
    2. ``ElementEditIntent`` via keyword shortcuts / structured model
    3. Compile intent → StudioCommand
    4. Fall back to legacy ``StudioNLCommandPlanner`` when intent is unknown
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
        nl_planner: StudioNLCommandPlanner | None = None,
        intent_parser: ElementEditIntentParser | None = None,
        intent_compiler: ElementEditIntentCompiler | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._use_llm = use_llm
        self._nl_planner = nl_planner or StudioNLCommandPlanner(
            settings=self._settings,
            use_llm=use_llm,
        )
        self._intent_parser = intent_parser or ElementEditIntentParser(
            settings=self._settings,
            use_llm=use_llm,
        )
        self._intent_compiler = intent_compiler or ElementEditIntentCompiler()

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

        scope_gate = self._scope_gate_for_note(comment, note)
        if scope_gate is not None:
            return scope_gate

        keyword_intents = self._intent_parser.parse_keyword_intents(
            note, bound_node_id=comment.node_id, scene=scene
        )
        if len(keyword_intents) > 1:
            commands: list = []
            reasons: list[str] = []
            confidence = 1.0
            for intent in keyword_intents:
                enriched = self._enrich_intent_refs(intent, comment)
                part = self._intent_compiler.compile(
                    enriched,
                    scene=scene,
                    bound_node_id=comment.node_id,
                    presentation_id=presentation,
                    slide_id=slide,
                )
                if part.commands:
                    commands.extend(part.commands)
                    reasons.extend(part.reasons)
                    confidence = min(confidence, part.confidence)
            if commands:
                return self._enforce_bound_targets(
                    StudioCommandPlan(
                        commands=tuple(commands),
                        reasons=tuple(dict.fromkeys(reasons)),
                        confidence=confidence,
                    ),
                    comment,
                    scene=scene,
                )

        intent = self._intent_parser.parse(
            note,
            bound_node_id=comment.node_id,
            scene=scene,
            scope_node_ids=list(comment.scope_node_ids),
        )
        if intent is not None:
            intent = self._enrich_intent_refs(intent, comment)
            plan = self._intent_compiler.compile(
                intent,
                scene=scene,
                bound_node_id=comment.node_id,
                presentation_id=presentation,
                slide_id=slide,
            )
            if plan.commands or plan.unsupported_reason:
                return self._enforce_bound_targets(plan, comment, scene=scene)

        # Wider scopes: do not force NL planner into single-node resolution.
        bound_for_nl = (
            comment.node_id
            if comment.scope
            in {ElementCommentScope.NODE, ElementCommentScope.NODE_AND_REFERENCES}
            else None
        )
        plan = self._nl_planner.plan_text(
            note,
            scene=scene,
            presentation_id=presentation,
            slide_id=slide,
            bound_node_id=bound_for_nl,
        )
        return self._enforce_bound_targets(plan, comment, scene=scene)

    @staticmethod
    def _enrich_intent_refs(intent, comment: ElementComment):
        if (
            comment.scope == ElementCommentScope.SELECTION
            and comment.scope_node_ids
            and intent.operation in {"distribute", "align", "resize"}
            and not intent.reference_node_ids
        ):
            return intent.model_copy(
                update={"reference_node_ids": list(comment.scope_node_ids)}
            )
        return intent

    @staticmethod
    def suggested_scope_for_note(note: str) -> ElementCommentScope | None:
        """Heuristic: recommend a wider scope when the note clearly spans multiple nodes."""
        text = note.strip().lower()
        if not text:
            return None
        if any(hint in text for hint in _MULTI_NODE_SCOPE_HINTS):
            if any(token in text for token in ("对齐", "align")):
                return ElementCommentScope.NODE_AND_REFERENCES
            return ElementCommentScope.SELECTION
        return None

    def _scope_gate_for_note(
        self,
        comment: ElementComment,
        note: str,
    ) -> StudioCommandPlan | None:
        if comment.scope != ElementCommentScope.NODE:
            return None
        suggested = self.suggested_scope_for_note(note)
        if suggested is None or suggested == ElementCommentScope.NODE:
            return None
        if any(keyword in note.lower() for keyword in _ALIGN_LEFT_KEYWORDS):
            return None
        return StudioCommandPlan(
            commands=(),
            reasons=(),
            unsupported_reason=(
                f"该评论像多节点操作，当前 scope=`node` 会硬绑定到 `{comment.node_id}`。"
                f"请将 scope 设为 `{suggested.value}`（并提供 scope_node_ids），"
                "或改写为只针对当前节点的描述。"
            ),
        )

    def _enforce_bound_targets(
        self,
        plan: StudioCommandPlan,
        comment: ElementComment,
        *,
        scene: RenderScene,
    ) -> StudioCommandPlan:
        if not plan.commands:
            return plan

        scope = comment.scope
        bound_node_id = comment.node_id

        if scope == ElementCommentScope.NODE:
            return self._enforce_node_only(plan, bound_node_id)

        region_ids = (
            _nodes_in_region(scene, comment.region_bbox)
            if scope == ElementCommentScope.REGION
            else set()
        )
        allowed = comment.allowed_node_ids(scene_node_ids=region_ids)
        if scope == ElementCommentScope.NODE_AND_REFERENCES:
            return self._enforce_node_and_references(plan, bound_node_id, allowed or {bound_node_id})

        if allowed is None:
            return plan

        return self._enforce_allowed_set(plan, bound_node_id=bound_node_id, allowed=allowed)

    @staticmethod
    def _enforce_node_only(
        plan: StudioCommandPlan,
        bound_node_id: str,
    ) -> StudioCommandPlan:
        rewritten: list[StudioCommand] = []
        for command in plan.commands:
            updates: dict[str, object] = {}
            if hasattr(command, "node_id"):
                updates["node_id"] = bound_node_id
            if hasattr(command, "target_node_ids"):
                updates["target_node_ids"] = [bound_node_id]
            if hasattr(command, "node_ids") and getattr(command, "node_ids", None) is not None:
                existing = list(command.node_ids or [])
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

    @staticmethod
    def _enforce_node_and_references(
        plan: StudioCommandPlan,
        bound_node_id: str,
        seed_allowed: set[str],
    ) -> StudioCommandPlan:
        rewritten: list[StudioCommand] = []
        for command in plan.commands:
            targets = command_target_node_ids(command)
            updates: dict[str, object] = {}
            if bound_node_id not in targets:
                if hasattr(command, "target_node_ids"):
                    existing_targets = list(command.target_node_ids or [])
                    updates["target_node_ids"] = [bound_node_id, *existing_targets]
                elif hasattr(command, "node_id"):
                    updates["node_id"] = bound_node_id
            if hasattr(command, "node_ids") and getattr(command, "node_ids", None) is not None:
                existing = list(command.node_ids or [])
                if bound_node_id not in existing:
                    updates["node_ids"] = [bound_node_id, *existing]
            rewritten.append(command.model_copy(update=updates) if updates else command)

        for command in rewritten:
            targets = command_target_node_ids(command)
            if bound_node_id not in targets:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason=(
                        f"多节点引用操作仍需包含绑定节点 `{bound_node_id}`。"
                    ),
                )
            _ = seed_allowed

        return StudioCommandPlan(
            commands=tuple(rewritten),
            reasons=plan.reasons,
            parsed_intent=plan.parsed_intent,
            confidence=plan.confidence,
            unsupported_reason=plan.unsupported_reason,
            uses_layout_fallback=plan.uses_layout_fallback,
        )

    @staticmethod
    def _enforce_allowed_set(
        plan: StudioCommandPlan,
        *,
        bound_node_id: str,
        allowed: set[str],
    ) -> StudioCommandPlan:
        for command in plan.commands:
            targets = command_target_node_ids(command)
            if not targets:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason="命令未声明目标节点。",
                )
            outside = sorted(targets - allowed)
            if outside:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason=(
                        f"命令目标超出评论作用域：{', '.join(outside)}。"
                        f"允许节点：{', '.join(sorted(allowed))}。"
                    ),
                )
            if bound_node_id not in targets and bound_node_id not in allowed:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason=f"作用域未包含绑定节点 `{bound_node_id}`。",
                )
        return plan


def _nodes_in_region(scene: RenderScene, bbox: dict[str, float] | None) -> set[str]:
    if not bbox:
        return set()
    try:
        x = float(bbox["x"])
        y = float(bbox["y"])
        width = float(bbox["width"])
        height = float(bbox["height"])
    except (KeyError, TypeError, ValueError):
        return set()
    x2, y2 = x + width, y + height
    matched: set[str] = set()
    for node in scene.nodes:
        if not _node_intersects(node, x, y, x2, y2):
            continue
        matched.add(node.id)
    return matched


def _node_intersects(node: RenderNode, x: float, y: float, x2: float, y2: float) -> bool:
    nx2 = node.x + node.width
    ny2 = node.y + node.height
    return not (nx2 < x or node.x > x2 or ny2 < y or node.y > y2)
