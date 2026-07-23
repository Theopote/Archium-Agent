"""Map natural-language Studio edit requests to StudioCommand plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.application.visual.nlp_parser import parse_natural_language
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.application.visual.hybrid_parser import create_hybrid_parser
from archium.domain.visual.parsed_intent import ParsedIntent
from archium.domain.visual.partial_edit_preservation import PARTIAL_EDIT_INTERACTION_RULE
from archium.domain.visual.render_scene import RenderScene, TextNode
from archium.domain.visual.studio_command import (
    FixOverflowCommand,
    IncreaseDrawingReadabilityCommand,
    RewriteTextCommand,
    StudioCommand,
)
from archium.infrastructure.llm.factory import create_llm_provider

_ONLY_MENTIONED_PATTERNS: tuple[str, ...] = (
    "只修改我提到的部分",
    "只改我提到的",
    "不要改其他",
    "其余保持不变",
    "其他保持不变",
    "only modify what i mentioned",
    "only change what i mentioned",
)

_NODE_ALIASES: dict[str, str] = {
    "标题": "title",
    "题目": "title",
    "主标题": "title",
    "正文": "body",
    "说明": "body",
    "主图": "hero",
    "图注": "caption",
    "来源": "source",
}

_OVERFLOW_KEYWORDS: tuple[str, ...] = (
    "修复溢出",
    "文字溢出",
    "文本溢出",
    "放不下",
    "fix overflow",
    "text overflow",
)

_DRAWING_READABILITY_KEYWORDS: tuple[str, ...] = (
    "提高图纸可读性",
    "增大图纸",
    "放大图纸",
    "放大总平面",
    "图纸太小",
    "图纸过小",
    "increase drawing readability",
    "enlarge drawing",
)

_REWRITE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"把[「\"']?(.+?)[」\"']?改(?:成|为)[：:\s]*[「\"']?(.+?)[」\"']?\s*$", "element_text"),
    (r"标题改(?:成|为)[：:\s]*(.+)$", "title_text"),
    (r"改写标题为[：:\s]*(.+)$", "title_text"),
    (r"将标题改(?:成|为)[：:\s]*(.+)$", "title_text"),
    (r"convert title to[:\s]+(.+)$", "title_text"),
    (r"rewrite title to[:\s]+(.+)$", "title_text"),
)


@dataclass(frozen=True)
class StudioCommandPlan:
    """Planned Studio commands derived from NL or preset intent."""

    commands: tuple[StudioCommand, ...]
    reasons: tuple[str, ...]
    parsed_intent: VisualEditIntent | None = None
    confidence: float = 1.0
    unsupported_reason: str | None = None
    uses_layout_fallback: bool = False


class StudioNLCommandPlanner:
    """Translate NL / preset intents into RenderScene-level Studio commands."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._use_llm = use_llm and self._settings.llm_configured
        llm_provider = create_llm_provider(self._settings) if self._use_llm else None
        self._hybrid_parser = create_hybrid_parser(llm_provider, use_llm=self._use_llm)

    def plan_text(
        self,
        text: str,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        bound_node_id: str | None = None,
    ) -> StudioCommandPlan:
        normalized = text.strip()
        if not normalized:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason="请输入修改描述。",
            )

        rewrite_plan = self._plan_rewrite_patterns(
            normalized,
            scene=scene,
            presentation_id=presentation_id,
            slide_id=slide_id,
            bound_node_id=bound_node_id,
        )
        if rewrite_plan is not None:
            return self._stamp_partial_edit_rule(rewrite_plan)

        if any(keyword in normalized.lower() for keyword in _OVERFLOW_KEYWORDS):
            node_ids = [bound_node_id] if bound_node_id else None
            return self._stamp_partial_edit_rule(
                self._overflow_plan(
                    scene=scene,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    reason="修复文本溢出",
                    node_ids=node_ids,
                )
            )

        drawing_plan = self._plan_drawing_readability_keywords(
            normalized,
            scene=scene,
            presentation_id=presentation_id,
            slide_id=slide_id,
            bound_node_id=bound_node_id,
        )
        if drawing_plan is not None:
            return self._stamp_partial_edit_rule(drawing_plan)

        parsed = self._hybrid_parser.parse(normalized)
        if parsed is None:
            intent, params = parse_natural_language(normalized)
            if intent is None:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    unsupported_reason=(
                        "无法识别 Scene 级修改意图。"
                        "可尝试：「标题改为…」「把正文改成…」「修复文字溢出」「减少文字」。"
                    ),
                )
            return self._stamp_partial_edit_rule(
                self._plan_intent(
                    intent,
                    params,
                    scene=scene,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    confidence=0.75,
                    bound_node_id=bound_node_id,
                )
            )

        if self._is_composite(parsed):
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                parsed_intent=parsed.intent,
                confidence=parsed.confidence,
                unsupported_reason="复合修改暂未纳入 Scene 提案，请拆成单步指令或改用版式直接编辑。",
                uses_layout_fallback=True,
            )

        return self._stamp_partial_edit_rule(
            self._plan_intent(
                parsed.intent,
                parsed.params,
                scene=scene,
                presentation_id=presentation_id,
                slide_id=slide_id,
                confidence=parsed.confidence,
                bound_node_id=bound_node_id,
            )
        )

    def plan_intent(
        self,
        intent: VisualEditIntent,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        params: dict[str, object] | None = None,
        bound_node_id: str | None = None,
    ) -> StudioCommandPlan:
        return self._stamp_partial_edit_rule(
            self._plan_intent(
                intent,
                params or {},
                scene=scene,
                presentation_id=presentation_id,
                slide_id=slide_id,
                confidence=1.0,
                bound_node_id=bound_node_id,
            )
        )

    @staticmethod
    def _stamp_partial_edit_rule(plan: StudioCommandPlan) -> StudioCommandPlan:
        """Always advertise the system-level partial-edit contract on successful plans."""
        if not plan.commands:
            return plan
        reasons = list(plan.reasons)
        if PARTIAL_EDIT_INTERACTION_RULE not in reasons:
            reasons.insert(0, PARTIAL_EDIT_INTERACTION_RULE)
        return StudioCommandPlan(
            commands=plan.commands,
            reasons=tuple(reasons),
            parsed_intent=plan.parsed_intent,
            confidence=plan.confidence,
            unsupported_reason=plan.unsupported_reason,
            uses_layout_fallback=plan.uses_layout_fallback,
        )

    def _plan_rewrite_patterns(
        self,
        text: str,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        bound_node_id: str | None = None,
    ) -> StudioCommandPlan | None:
        lowered = text.lower()
        for pattern, kind in _REWRITE_PATTERNS:
            match = re.search(pattern, lowered if kind == "title_text" else text, re.IGNORECASE)
            if not match:
                continue
            if kind == "title_text":
                new_text = match.group(1).strip()
                node_id = _resolve_target_node_id(scene, "title", bound_node_id=bound_node_id)
            else:
                element_hint = match.group(1).strip()
                new_text = match.group(2).strip()
                node_id = _resolve_target_node_id(
                    scene, element_hint, bound_node_id=bound_node_id
                )
            if not new_text:
                continue
            command = RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=slide_id,
                node_id=node_id,
                target_node_ids=[node_id],
                new_text=new_text,
                reason="rewrite text from natural language",
                expected_effect=f"改写 `{node_id}` 文本",
            )
            return StudioCommandPlan(
                commands=(command,),
                reasons=(command.expected_effect,),
                parsed_intent=VisualEditIntent.UPDATE_ELEMENT_TEXT,
                confidence=0.95,
            )
        return None

    def _plan_intent(
        self,
        intent: VisualEditIntent,
        params: dict[str, object],
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        confidence: float,
        bound_node_id: str | None = None,
    ) -> StudioCommandPlan:
        if intent == VisualEditIntent.REDUCE_TEXT:
            node_ids = None
            if bound_node_id:
                node_ids = [bound_node_id]
            else:
                element_id = params.get("element_id")
                if isinstance(element_id, str) and element_id.strip():
                    node_ids = [resolve_render_node_id(scene, element_id)]
            return self._overflow_plan(
                scene=scene,
                presentation_id=presentation_id,
                slide_id=slide_id,
                node_ids=node_ids,
                reason="减少文字 / 修复溢出",
                parsed_intent=intent,
                confidence=confidence,
            )

        if intent == VisualEditIntent.UPDATE_ELEMENT_TEXT:
            new_text = str(params.get("text") or params.get("new_text") or "").strip()
            element_id = str(params.get("element_id") or "title").strip()
            if not new_text:
                return StudioCommandPlan(
                    commands=(),
                    reasons=(),
                    parsed_intent=intent,
                    confidence=confidence,
                    unsupported_reason="更新文字需要提供目标元素和新文本内容。",
                )
            node_id = _resolve_target_node_id(
                scene, element_id, bound_node_id=bound_node_id
            )
            command = RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=slide_id,
                node_id=node_id,
                target_node_ids=[node_id],
                new_text=new_text,
                reason="update element text",
                expected_effect=f"更新 `{node_id}` 文本",
            )
            return StudioCommandPlan(
                commands=(command,),
                reasons=(command.expected_effect,),
                parsed_intent=intent,
                confidence=confidence,
            )

        layout_only = {
            VisualEditIntent.INCREASE_WHITESPACE,
            VisualEditIntent.CHANGE_LAYOUT,
            VisualEditIntent.SET_HERO_ASSET,
            VisualEditIntent.REMOVE_ASSET,
            VisualEditIntent.SET_ELEMENT_ASSET,
            VisualEditIntent.LOCK_ELEMENT,
            VisualEditIntent.UNLOCK_ELEMENT,
            VisualEditIntent.MOVE_ELEMENT,
            VisualEditIntent.RESIZE_ELEMENT,
        }
        if intent == VisualEditIntent.ENLARGE_HERO:
            drawing_id = bound_node_id or _default_drawing_node_id(scene)
            if drawing_id is not None:
                return self._drawing_readability_plan(
                    scene=scene,
                    presentation_id=presentation_id,
                    slide_id=slide_id,
                    node_id=drawing_id,
                    reason="放大主图/图纸以提升可读性",
                    parsed_intent=intent,
                    confidence=confidence,
                )
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                parsed_intent=intent,
                confidence=confidence,
                unsupported_reason=(
                    "当前页未找到图纸节点，无法生成图纸可读性提案。"
                ),
                uses_layout_fallback=True,
            )

        if intent in layout_only:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                parsed_intent=intent,
                confidence=confidence,
                unsupported_reason=(
                    f"「{intent.value}」仍走 LayoutPlan 直接编辑，暂未纳入 Scene 修改提案。"
                ),
                uses_layout_fallback=True,
            )

        return StudioCommandPlan(
            commands=(),
            reasons=(),
            parsed_intent=intent,
            confidence=confidence,
            unsupported_reason=f"暂不支持将 `{intent.value}` 转为 Scene 命令。",
        )

    def _overflow_plan(
        self,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        reason: str,
        node_ids: list[str] | None = None,
        parsed_intent: VisualEditIntent | None = None,
        confidence: float = 0.9,
    ) -> StudioCommandPlan:
        command = FixOverflowCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_ids=node_ids,
            target_node_ids=list(node_ids or []),
            reason=reason,
            expected_effect="修复文本溢出",
        )
        return StudioCommandPlan(
            commands=(command,),
            reasons=(command.expected_effect,),
            parsed_intent=parsed_intent or VisualEditIntent.REDUCE_TEXT,
            confidence=confidence,
        )

    def _plan_drawing_readability_keywords(
        self,
        text: str,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        bound_node_id: str | None = None,
    ) -> StudioCommandPlan | None:
        lowered = text.lower()
        if not any(keyword in lowered for keyword in _DRAWING_READABILITY_KEYWORDS):
            return None
        node_id = bound_node_id or _default_drawing_node_id(scene)
        if node_id is None:
            return StudioCommandPlan(
                commands=(),
                reasons=(),
                unsupported_reason="当前页未找到可放大的图纸节点。",
            )
        return self._drawing_readability_plan(
            scene=scene,
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=node_id,
            reason="提高图纸可读性",
        )

    def _drawing_readability_plan(
        self,
        *,
        scene: RenderScene,
        presentation_id: UUID,
        slide_id: UUID,
        node_id: str,
        reason: str,
        parsed_intent: VisualEditIntent | None = None,
        confidence: float = 0.9,
    ) -> StudioCommandPlan:
        command = IncreaseDrawingReadabilityCommand(
            presentation_id=presentation_id,
            slide_id=slide_id,
            node_id=node_id,
            target_node_ids=[node_id],
            reason=reason,
            expected_effect=f"扩大图纸 `{node_id}` 并压缩辅助正文",
        )
        return StudioCommandPlan(
            commands=(command,),
            reasons=(command.expected_effect,),
            parsed_intent=parsed_intent,
            confidence=confidence,
        )

    @staticmethod
    def _is_composite(parsed: ParsedIntent) -> bool:
        has_constraints = any(modifier.type.value == "constraint" for modifier in parsed.modifiers)
        has_multi_step = any(modifier.type.value == "multi_step" for modifier in parsed.modifiers)
        return has_constraints or has_multi_step or "multi_step_operations" in parsed.params


def _resolve_target_node_id(
    scene: RenderScene,
    hint: str | None,
    *,
    bound_node_id: str | None = None,
) -> str:
    """Prefer a hard-bound node id over fuzzy hint resolution."""
    if bound_node_id:
        node = scene.node_by_id(bound_node_id)
        if node is None:
            raise ValueError(f"绑定节点不存在：`{bound_node_id}`")
        return bound_node_id
    return resolve_render_node_id(scene, hint)


def resolve_render_node_id(scene: RenderScene, hint: str | None, *, default: str = "title") -> str:
    """Resolve a user hint to a RenderScene node id."""
    token = (hint or default).strip()
    if not token:
        token = default
    normalized = _NODE_ALIASES.get(token, token)

    direct = scene.node_by_id(normalized)
    if direct is not None:
        return direct.id

    for node in scene.nodes:
        if node.source_layout_element_id == normalized:
            return node.id
        if node.semantic_role == normalized:
            return node.id
        if normalized in node.id:
            return node.id

    if normalized in {"title", "heading", "central_claim"}:
        for node in scene.nodes:
            if isinstance(node, TextNode) and node.semantic_role in {
                "title",
                "heading",
                "central_claim",
            }:
                return node.id
        for node in scene.nodes:
            if isinstance(node, TextNode):
                return node.id

    raise ValueError(f"无法在 RenderScene 中定位节点：`{hint}`")


def _default_drawing_node_id(scene: RenderScene) -> str | None:
    for node in scene.nodes:
        if getattr(node, "node_type", "") == "drawing":
            return node.id
    for node in scene.nodes:
        if "plan" in node.id or "drawing" in node.id:
            return node.id
    return None
