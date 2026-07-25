"""Derive SpatialIntent / DesignRules from ConceptDirection fields (rules, not Agent)."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.spatial_design import DesignDecision, DesignRule, SpatialIntent


def spatial_intent_from_direction(direction: ConceptDirection) -> SpatialIntent | None:
    """Build SpatialIntent from structured direction text (deterministic heuristics)."""
    if direction.spatial_intent is not None and not direction.spatial_intent.is_empty():
        return direction.spatial_intent

    spatial = (direction.spatial_strategy or direction.spatial_idea or "").strip()
    formal = (direction.formal_language or "").strip()
    material = (direction.material_strategy or "").strip()
    experience = (direction.experience_focus or "").strip()
    if not any((spatial, formal, material, experience)):
        return None

    landscape = ""
    relationships = spatial
    lower = f"{spatial} {formal} {material}".lower()
    if any(token in lower for token in ("山", "地形", "嵌入", "台地", "等高", "embed", "terrain")):
        landscape = "嵌入/顺应地形，减少对地貌的对立切割"
    elif any(token in lower for token in ("院", "庭", "围合", "courtyard")):
        landscape = "以内向院落组织建筑与自然的渗透"
    elif any(token in lower for token in ("景观", "渗透", "公园", "绿")):
        landscape = "建筑与景观相互渗透，边界柔化"

    movement = experience
    if not movement and any(token in lower for token in ("路径", "流线", "环", "序列", "path")):
        movement = "以路径/序列组织体验节奏"

    public_private = ""
    if any(token in lower for token in ("院", "共享", "公共", "私密", "单元")):
        public_private = "公共共享核 + 私密单元分层"

    light = ""
    if any(token in lower for token in ("光", "采光", "明暗", "light", "shadow")):
        light = "以自然光与明暗节奏强化空间体验"
    elif material and any(token in material for token in ("石", "木", "土", "砖")):
        light = "材料表情与侧光/天光共同塑造氛围"

    intent = SpatialIntent(
        spatial_relationships=relationships[:500],
        movement_experience=movement[:400],
        public_private_structure=public_private[:400],
        light_strategy=light[:400],
        landscape_relation=landscape[:400],
    )
    return None if intent.is_empty() else intent


def design_rules_from_direction(direction: ConceptDirection) -> list[DesignRule]:
    """Expand concept slogan into spatial / formal / evaluation rules."""
    if direction.design_rules:
        return [rule for rule in direction.design_rules if not rule.is_empty()]

    rules: list[DesignRule] = []
    spatial = (direction.spatial_strategy or direction.spatial_idea or "").strip()
    formal = (direction.formal_language or "").strip()
    material = (direction.material_strategy or "").strip()
    theme = (direction.theme or direction.title or "").strip()
    risks = [r.strip() for r in direction.risks if r and r.strip()]

    if spatial:
        rules.append(
            DesignRule(
                principle=theme or "空间组织原则",
                spatial_translation=spatial,
                formal_translation=formal or _formal_hint_from_spatial(spatial),
                evaluation_method=_evaluation_for_spatial(spatial),
                confidence=0.62 if formal else 0.5,
            )
        )
    if formal and (not rules or formal not in (rules[0].formal_translation or "")):
        rules.append(
            DesignRule(
                principle="形式语言一致性",
                spatial_translation=spatial[:200] if spatial else "形式服从空间组织",
                formal_translation=formal,
                evaluation_method="形式语言是否与空间策略一致、是否避免风格空转？",
                confidence=0.55,
            )
        )
    if material:
        rules.append(
            DesignRule(
                principle="材料与构造态度",
                spatial_translation="材料表达强化空间氛围与场所归属",
                formal_translation=material,
                evaluation_method="材料是否回应气候/工艺/地域，而非贴皮装饰？",
                confidence=0.58,
            )
        )
    if risks:
        rules.append(
            DesignRule(
                principle="风险边界",
                spatial_translation=risks[0],
                formal_translation="",
                evaluation_method="方案是否主动回应已识别风险？",
                confidence=0.45,
            )
        )
    return [rule for rule in rules if not rule.is_empty()][:6]


def ensure_direction_spatial_layer(direction: ConceptDirection) -> ConceptDirection:
    """Fill spatial_intent + design_rules when missing (idempotent)."""
    updates: dict[str, object] = {}
    if direction.spatial_intent is None or direction.spatial_intent.is_empty():
        intent = spatial_intent_from_direction(direction)
        if intent is not None:
            updates["spatial_intent"] = intent
    if not direction.design_rules:
        rules = design_rules_from_direction(
            direction.model_copy(update=updates) if updates else direction
        )
        if rules:
            updates["design_rules"] = rules
    if not updates:
        return direction
    return direction.model_copy(update=updates)


def design_decision_from_direction_selection(
    direction: ConceptDirection,
    *,
    previous_theme: str = "",
) -> DesignDecision:
    """Record selecting a concept direction as a DesignDecision."""
    alternatives = []
    # open_questions / risks as soft alternatives context
    for risk in direction.risks[:3]:
        if risk.strip():
            alternatives.append(f"风险备忘：{risk.strip()}")
    return DesignDecision(
        decision=f"选定概念方向：{direction.title}",
        alternatives=alternatives,
        chosen=direction.title,
        reason=(
            direction.design_rationale.statement
            if direction.design_rationale and direction.design_rationale.statement.strip()
            else (direction.spatial_strategy or direction.summary or direction.theme)
        )[:500],
        evidence=[
            *(direction.design_rationale.evidence[:4] if direction.design_rationale else []),
            *([f"空间策略：{direction.spatial_strategy}"] if direction.spatial_strategy.strip() else []),
        ][:8],
        impact=(
            "空间组织 / 形式语言 / 材料策略进入 DesignIntent.spatial_intent 与 design_rules；"
            "后续概念视觉与汇报应以此为约束。"
            + (f" 先前主题：「{previous_theme}」。" if previous_theme.strip() else "")
        )[:500],
        direction_id=str(direction.id),
        direction_title=direction.title,
    )


def _formal_hint_from_spatial(spatial: str) -> str:
    lower = spatial.lower()
    if any(t in lower for t in ("嵌入", "山", "台地", "embed")):
        return "低矮水平延展，减少暴露体量"
    if any(t in lower for t in ("院", "围合", "courtyard")):
        return "围合界面 + 内向公共核"
    if any(t in lower for t in ("轴", "对称", "axis")):
        return "轴线控制体量与虚空"
    return "形式服从空间策略，避免风格先行"


def _evaluation_for_spatial(spatial: str) -> str:
    lower = spatial.lower()
    if any(t in lower for t in ("山", "地形", "嵌入", "台地")):
        return "是否减少视觉影响？是否保持地形连续？是否增强山地体验？"
    if any(t in lower for t in ("院", "围合")):
        return "是否形成共享中心？是否兼顾采光与私密？"
    return "空间策略是否可被平面/剖面验证？是否回应场地与使用？"
