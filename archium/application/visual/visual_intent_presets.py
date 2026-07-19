"""Preset mutations for VisualIntent before layout replanning."""

from __future__ import annotations

from uuid import UUID

from archium.domain.enums import ApprovalStatus
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.visual_intent import VisualIntent

_PRESET_FAMILY: dict[str, LayoutFamily] = {
    "drawing_focus": LayoutFamily.DRAWING_FOCUS,
    "evidence_board": LayoutFamily.EVIDENCE_BOARD,
    "hero": LayoutFamily.HERO,
    "textual_argument": LayoutFamily.TEXTUAL_ARGUMENT,
    "strategy_cards": LayoutFamily.STRATEGY_CARDS,
    "comparative_matrix": LayoutFamily.COMPARATIVE_MATRIX,
}


def apply_visual_intent_preset(intent: VisualIntent, preset: str | None) -> VisualIntent:
    if not preset:
        return intent
    updates: dict[str, object] = {}
    if preset == "reduce_text":
        updates["density_level"] = DensityLevel.SPACIOUS
        updates["composition_strategy"] = "减少文字，突出主信息"
    elif preset == "enlarge_hero":
        updates["composition_strategy"] = "放大主图，压缩辅助文字"
        updates["density_level"] = DensityLevel.SPACIOUS
    elif preset == "more_whitespace":
        updates["density_level"] = DensityLevel.SPACIOUS
        updates["composition_strategy"] = "增加留白，降低信息密度"
    elif preset == "drawing_focus":
        updates["preferred_layout_families"] = [LayoutFamily.DRAWING_FOCUS]
        updates["dominant_content_type"] = VisualContentType.SITE_PLAN
        updates["image_treatment"] = "drawing_contain"
        updates["composition_strategy"] = "图纸优先"
    elif preset in _PRESET_FAMILY:
        family = _PRESET_FAMILY[preset]
        updates["preferred_layout_families"] = [family]
        updates["composition_strategy"] = f"切换到 {family.value}"
    if not updates:
        return intent
    updated = intent.model_copy(update={**updates, "version": intent.version + 1})
    updated.approval_status = ApprovalStatus.PENDING
    updated.touch()
    return updated


def apply_layout_family_preference(
    intent: VisualIntent,
    layout_family: LayoutFamily,
) -> VisualIntent:
    updated = intent.model_copy(
        update={
            "preferred_layout_families": [layout_family],
            "composition_strategy": f"切换到 {layout_family.value}",
            "version": intent.version + 1,
            "approval_status": ApprovalStatus.PENDING,
        }
    )
    updated.touch()
    return updated


def apply_hero_asset(intent: VisualIntent, asset_id: UUID) -> VisualIntent:
    supporting = [item for item in intent.supporting_asset_ids if item != asset_id]
    updated = intent.model_copy(
        update={
            "hero_asset_id": asset_id,
            "supporting_asset_ids": supporting,
            "version": intent.version + 1,
            "approval_status": ApprovalStatus.PENDING,
        }
    )
    updated.touch()
    return updated


def remove_primary_asset(intent: VisualIntent) -> VisualIntent:
    supporting = list(intent.supporting_asset_ids)
    hero = intent.hero_asset_id
    if hero is not None:
        updated = intent.model_copy(
            update={
                "hero_asset_id": supporting[0] if supporting else None,
                "supporting_asset_ids": supporting[1:],
                "version": intent.version + 1,
                "approval_status": ApprovalStatus.PENDING,
            }
        )
    elif supporting:
        updated = intent.model_copy(
            update={
                "supporting_asset_ids": supporting[:-1],
                "version": intent.version + 1,
                "approval_status": ApprovalStatus.PENDING,
            }
        )
    else:
        return intent
    updated.touch()
    return updated
