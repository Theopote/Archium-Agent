"""Parse element comments into ElementEditIntent (keywords + structured model)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field

from archium.application.agent_skills import apply_skills_to_request
from archium.config.settings import Settings, get_settings
from archium.domain.visual.element_edit_intent import (
    ElementEditIntent,
    ElementEditOperation,
)
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.factory import create_llm_provider

_DEFAULT_MOVE_IN = 0.25
_DEFAULT_SCALE_UP = 1.15
_DEFAULT_SCALE_DOWN = 0.85


@dataclass(frozen=True)
class _KeywordShortcut:
    """High-confidence phrase → partially filled intent (not an open-ended pile)."""

    patterns: tuple[str, ...]
    operation: ElementEditOperation
    direction: str | None = None
    amount: float | None = None
    locked: bool | None = None
    visible: bool | None = None
    match_dimension: str | None = None
    confidence: float = 0.95


# Compact shortcut table — prefer structured fields over new one-off phrases.
_KEYWORD_SHORTCUTS: tuple[_KeywordShortcut, ...] = (
    # resize
    _KeywordShortcut(("缩小一点", "缩小", "减小", "小一点", "scale down", "make smaller"), "resize", "in", _DEFAULT_SCALE_DOWN),
    _KeywordShortcut(("放大一点", "放大", "增大", "大一点", "enlarge", "scale up", "make bigger"), "resize", "out", _DEFAULT_SCALE_UP),
    # move
    _KeywordShortcut(("向左移", "往左移", "左移", "move left", "nudge left"), "move", "left", _DEFAULT_MOVE_IN),
    _KeywordShortcut(("向右移", "往右移", "右移", "move right", "nudge right"), "move", "right", _DEFAULT_MOVE_IN),
    _KeywordShortcut(("向上移", "往上移", "上移", "move up", "nudge up"), "move", "up", _DEFAULT_MOVE_IN),
    _KeywordShortcut(("向下移", "往下移", "下移", "move down", "nudge down"), "move", "down", _DEFAULT_MOVE_IN),
    # align
    _KeywordShortcut(("和左边对齐", "与左边对齐", "左对齐", "靠左", "align left"), "align", "left"),
    _KeywordShortcut(("和右边对齐", "与右边对齐", "右对齐", "靠右", "align right"), "align", "right"),
    _KeywordShortcut(("与顶部对齐", "和顶部对齐", "顶对齐", "靠上", "align top"), "align", "top"),
    _KeywordShortcut(("与底部对齐", "和底部对齐", "底对齐", "靠下", "align bottom"), "align", "bottom"),
    _KeywordShortcut(("与中心对齐", "和中心对齐", "居中对齐", "水平居中", "align center"), "align", "center"),
    _KeywordShortcut(("垂直居中", "与中间对齐", "align middle"), "align", "middle"),
    # match size
    _KeywordShortcut(("与.*等宽", "等宽", "同样宽", "same width", "match width"), "resize", None, None, match_dimension="width"),
    _KeywordShortcut(("与.*等高", "等高", "同样高", "same height", "match height"), "resize", None, None, match_dimension="height"),
    # visibility / lock / reorder
    _KeywordShortcut(("隐藏", "hide", "invisible"), "visibility", visible=False),
    _KeywordShortcut(("显示", "取消隐藏", "show", "unhide"), "visibility", visible=True),
    _KeywordShortcut(("解锁", "unlock"), "lock", locked=False),
    _KeywordShortcut(("锁定", "lock"), "lock", locked=True),
    _KeywordShortcut(("置顶", "到最前", "bring to front", "to front"), "reorder", "front"),
    _KeywordShortcut(("置底", "到最后", "send to back", "to back"), "reorder", "back"),
    _KeywordShortcut(("上移一层", "前移一层", "bring forward"), "reorder", "forward"),
    _KeywordShortcut(("下移一层", "后移一层", "send backward"), "reorder", "backward"),
    # distribute
    _KeywordShortcut(("水平分布", "横向分布", "distribute horizontally"), "distribute", "horizontal"),
    _KeywordShortcut(("垂直分布", "纵向分布", "distribute vertically"), "distribute", "vertical"),
)


class ElementEditIntentDraft(BaseModel):
    """LLM structured-output twin of ElementEditIntent."""

    operation: ElementEditOperation
    direction: str | None = None
    amount: float | None = None
    reference_node_ids: list[str] = Field(default_factory=list)
    text_value: str | None = None
    color_value: str | None = None
    font_size: float | None = None
    asset_uri: str | None = None
    asset_id: str | None = None
    locked: bool | None = None
    visible: bool | None = None
    match_dimension: str | None = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    rationale: str = ""


_SYSTEM_PROMPT = """你是建筑汇报幻灯片的元素编辑意图解析器。
把用户对「当前选中节点」的自然语言评论解析为 JSON（ElementEditIntent）。

operation 只能是：
move | resize | align | distribute | replace_asset | rewrite_text |
change_style | visibility | lock | reorder

字段说明：
- direction: left/right/up/down/in/out/top/bottom/center/middle/front/back/forward/backward/horizontal/vertical
- amount: 移动用英寸；缩放用倍率（如 0.85 / 1.15）；可空
- reference_node_ids: 对齐/等宽参考节点 id 列表
- text_value: rewrite_text 的新文案
- color_value: change_style 的颜色（#RRGGBB）
- font_size: 字号 pt
- asset_uri / asset_id: replace_asset
- locked / visible: lock / visibility
- match_dimension: width | height | both（等宽/等高）
- confidence: 0~1

只输出 JSON，不要解释。"""


class ElementEditIntentParser:
    """Keywords = high-confidence shortcuts; otherwise structured-output model."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        use_llm: bool = False,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._use_llm = bool(use_llm and self._settings.llm_configured)
        self._llm = llm_provider
        if self._use_llm and self._llm is None:
            self._llm = create_llm_provider(self._settings)

    def parse(
        self,
        note: str,
        *,
        bound_node_id: str,
        scene: RenderScene,
        scope_node_ids: list[str] | None = None,
    ) -> ElementEditIntent | None:
        text = note.strip()
        if not text:
            return None

        shortcuts = self.parse_keyword_intents(
            text, scene=scene, bound_node_id=bound_node_id
        )
        if len(shortcuts) == 1 and shortcuts[0].confidence >= 0.85:
            return shortcuts[0]
        if len(shortcuts) > 1:
            # Multi-intent keyword phrases are handled by the planner via parse_keyword_intents.
            return None

        structured = self._parse_structured_heuristics(
            text, scene=scene, bound_node_id=bound_node_id
        )
        if structured is not None and structured.confidence >= 0.8:
            return structured

        if self._use_llm and self._llm is not None:
            draft = self._parse_with_llm(
                text,
                bound_node_id=bound_node_id,
                scene=scene,
                scope_node_ids=scope_node_ids or [],
            )
            if draft is not None:
                return draft

        return structured or (shortcuts[0] if shortcuts else None)

    def parse_keyword_intents(
        self,
        note: str,
        *,
        bound_node_id: str,
        scene: RenderScene,
    ) -> list[ElementEditIntent]:
        """Return all high-confidence keyword shortcuts (supports compound notes)."""
        text = note.strip()
        if not text:
            return []
        lowered = text.lower()
        matched: list[ElementEditIntent] = []
        seen_ops: set[tuple[str, str | None]] = set()
        for rule in _KEYWORD_SHORTCUTS:
            if not any(
                (pattern.lower() in lowered)
                if ".*" not in pattern
                else bool(re.search(pattern, text, re.I))
                for pattern in rule.patterns
            ):
                continue
            # Disambiguate nested antonyms (unlock⊃lock, 取消隐藏⊃隐藏).
            if (
                rule.operation == "lock"
                and rule.locked is True
                and any(token in lowered for token in ("unlock", "解锁"))
            ):
                continue
            if rule.operation == "visibility" and rule.visible is False and any(
                token in lowered
                for token in ("unhide", "show", "显示", "取消隐藏")
            ):
                continue
            key = (rule.operation, rule.direction or rule.match_dimension)
            if key in seen_ops:
                continue
            # Avoid lock+unlock both firing from "解锁".
            if rule.operation == "lock" and any(
                intent.operation == "lock" for intent in matched
            ):
                continue
            seen_ops.add(key)
            amount = _extract_amount(text, default=rule.amount)
            refs = _extract_reference_node_ids(text, scene=scene, bound_node_id=bound_node_id)
            if rule.match_dimension and not refs:
                refs = _nearest_sibling_ids(scene, bound_node_id, limit=1)
            matched.append(
                ElementEditIntent(
                    operation=rule.operation,
                    direction=rule.direction,
                    amount=amount,
                    reference_node_ids=refs,
                    locked=rule.locked,
                    visible=rule.visible,
                    match_dimension=rule.match_dimension,  # type: ignore[arg-type]
                    confidence=rule.confidence,
                    source="keyword",
                    rationale=f"keyword shortcut → {rule.operation}",
                )
            )
        return matched

    def _parse_keyword_shortcut(
        self,
        text: str,
        *,
        scene: RenderScene,
        bound_node_id: str,
    ) -> ElementEditIntent | None:
        intents = self.parse_keyword_intents(
            text, scene=scene, bound_node_id=bound_node_id
        )
        return intents[0] if intents else None

    def _parse_structured_heuristics(
        self,
        text: str,
        *,
        scene: RenderScene,
        bound_node_id: str,
    ) -> ElementEditIntent | None:
        """Deterministic field extraction for common templates (not keyword sprawl)."""
        color = _extract_color(text)
        # Prefer style when a color token is present (avoid rewrite stealing 「改为 #FF0000」).
        if (
            color
            and any(
                token in text.lower()
                for token in ("颜色", "colour", "color", "改成", "改为")
            )
            and (
                any(token in text for token in ("颜色", "colour", "color"))
                or color in text
            )
        ):
            return ElementEditIntent(
                operation="change_style",
                color_value=color,
                confidence=0.88,
                source="heuristic",
                rationale="color style template",
            )

        rewrite = _extract_rewrite_text(text)
        if rewrite:
            return ElementEditIntent(
                operation="rewrite_text",
                text_value=rewrite,
                confidence=0.9,
                source="heuristic",
                rationale="rewrite template",
            )

        font_size = _extract_font_size(text)
        if font_size is not None:
            return ElementEditIntent(
                operation="change_style",
                font_size=font_size,
                confidence=0.86,
                source="heuristic",
                rationale="font size template",
            )

        asset_uri = _extract_asset_uri(text)
        if asset_uri and any(token in text for token in ("替换", "换成", "replace")):
            return ElementEditIntent(
                operation="replace_asset",
                asset_uri=asset_uri,
                confidence=0.85,
                source="heuristic",
                rationale="replace asset uri",
            )

        # Relative nudge with explicit distance: 向左移动0.5英寸
        move = re.search(
            r"(?:向|往)?(左|右|上|下)(?:移动|移)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:英寸|in)?",
            text,
        )
        if move:
            direction_map = {"左": "left", "右": "right", "上": "up", "下": "down"}
            return ElementEditIntent(
                operation="move",
                direction=direction_map[move.group(1)],
                amount=float(move.group(2)),
                confidence=0.9,
                source="heuristic",
                rationale="move with amount",
            )

        return None

    def _parse_with_llm(
        self,
        text: str,
        *,
        bound_node_id: str,
        scene: RenderScene,
        scope_node_ids: list[str],
    ) -> ElementEditIntent | None:
        assert self._llm is not None
        node_catalog = [
            {
                "id": node.id,
                "type": getattr(node, "node_type", type(node).__name__),
                "role": getattr(node, "semantic_role", "") or "",
            }
            for node in scene.nodes
            if node.visible
        ]
        user_prompt = (
            f"bound_node_id={bound_node_id}\n"
            f"scope_node_ids={scope_node_ids}\n"
            f"nodes={node_catalog[:40]}\n"
            f"comment={text}"
        )
        try:
            request, _audit = apply_skills_to_request(
                LLMRequest(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.1,
                    json_mode=True,
                ),
                task_type="element_edit_intent",
                inject_bodies=True,
                limit=3,
            )
            draft = self._llm.generate_structured(
                request,
                ElementEditIntentDraft,
            )
        except Exception:
            return None
        if draft.confidence < 0.5:
            return None
        asset_id = None
        if draft.asset_id:
            try:
                asset_id = UUID(str(draft.asset_id))
            except ValueError:
                asset_id = None
        match_dim = draft.match_dimension if draft.match_dimension in {"width", "height", "both"} else None
        return ElementEditIntent(
            operation=draft.operation,
            direction=draft.direction,
            amount=draft.amount,
            reference_node_ids=list(draft.reference_node_ids),
            text_value=draft.text_value,
            color_value=draft.color_value,
            font_size=draft.font_size,
            asset_uri=draft.asset_uri,
            asset_id=asset_id,
            locked=draft.locked,
            visible=draft.visible,
            match_dimension=cast(Literal["width", "height", "both"] | None, match_dim),
            confidence=draft.confidence,
            source="structured_model",
            rationale=draft.rationale or "llm structured intent",
        )


def _extract_amount(text: str, *, default: float | None) -> float | None:
    explicit = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:英寸|in|倍)?", text)
    if explicit:
        value = float(explicit.group(1))
        # Heuristic: bare integers like "一层" shouldn't win; require unit or decimal for move.
        if "." in explicit.group(1) or "英寸" in text or "in" in text.lower() or "倍" in text:
            return value
    if default is None:
        return None
    if "一点" in text or "稍微" in text or "a bit" in text.lower():
        if default >= 1.0:
            return min(default, 1.1)
        return min(default, 0.15) if default < 0.5 else default
    return default


def _extract_rewrite_text(text: str) -> str | None:
    patterns = (
        r"(?:改(?:成|为)|改写(?:成|为)?|换成|替换为)[：:\s]*[「\"'](.+?)[」\"']\s*$",
        r"(?:改(?:成|为)|改写(?:成|为)?|换成|替换为)[：:\s]*(.+)$",
        r"(?:rewrite|change(?:\s+text)?\s+to)[:\s]+[\"'](.+?)[\"']\s*$",
        r"(?:rewrite|change(?:\s+text)?\s+to)[:\s]+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).strip()
            if value and not any(token in value for token in ("颜色", "图片", "图纸")):
                return value
    return None


def _extract_color(text: str) -> str | None:
    hex_match = re.search(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", text)
    if hex_match:
        raw = hex_match.group(1)
        if len(raw) == 3:
            raw = "".join(ch * 2 for ch in raw)
        return f"#{raw.upper()}"
    named = {
        "红色": "#E53935",
        "蓝色": "#1E88E5",
        "黑色": "#111111",
        "白色": "#FFFFFF",
        "灰色": "#757575",
        "red": "#E53935",
        "blue": "#1E88E5",
        "black": "#111111",
        "white": "#FFFFFF",
        "gray": "#757575",
        "grey": "#757575",
    }
    lowered = text.lower()
    for name, value in named.items():
        if name in text or name in lowered:
            return value
    return None


def _extract_font_size(text: str) -> float | None:
    match = re.search(r"(?:字号|字体大小|font\s*size)\s*[：: ]*\s*([0-9]+(?:\.[0-9]+)?)\s*pt?", text, re.I)
    if match:
        return float(match.group(1))
    return None


def _extract_asset_uri(text: str) -> str | None:
    match = re.search(r"(project://\S+|asset://\S+|https?://\S+)", text)
    return match.group(1).rstrip(")。,]}") if match else None


def _extract_reference_node_ids(
    text: str,
    *,
    scene: RenderScene,
    bound_node_id: str,
) -> list[str]:
    ids: list[str] = []
    for node in scene.nodes:
        if node.id == bound_node_id:
            continue
        if node.id in text:
            ids.append(node.id)
    if ids:
        return ids
    # soft role hints
    role_hints = {
        "左边": "left",
        "右侧": "right",
        "左边的文字": "left_text",
        "下面": "below",
    }
    if any(hint in text for hint in role_hints):
        return _nearest_sibling_ids(scene, bound_node_id, limit=1)
    return []


def _nearest_sibling_ids(scene: RenderScene, node_id: str, *, limit: int = 1) -> list[str]:
    node = scene.node_by_id(node_id)
    if node is None:
        return []
    scored: list[tuple[float, str]] = []
    for other in scene.nodes:
        if other.id == node_id or not other.visible:
            continue
        dx = (other.x + other.width / 2) - (node.x + node.width / 2)
        dy = (other.y + other.height / 2) - (node.y + node.height / 2)
        scored.append((dx * dx + dy * dy, other.id))
    scored.sort(key=lambda item: item[0])
    return [item[1] for item in scored[:limit]]
