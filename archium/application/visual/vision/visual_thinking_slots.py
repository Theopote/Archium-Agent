"""Visual Thinking slots — architect-facing exploration modes bound to DesignIntent."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.concept_direction import ConceptDirection
from archium.domain.visual.vision_generation import ArchitectureImageType, VisionStylePreset


@dataclass(frozen=True)
class VisualThinkingSlot:
    """One Visual Thinking lane (not a bare「生成图片」button)."""

    key: str
    label: str
    caption: str
    image_type: ArchitectureImageType
    style_preset: VisionStylePreset
    intent_field: str  # which DesignIntent / direction field this slot expresses


VISUAL_THINKING_SLOTS: tuple[VisualThinkingSlot, ...] = (
    VisualThinkingSlot(
        key="atmosphere",
        label="氛围草图",
        caption="空间气质与体验氛围",
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        style_preset=VisionStylePreset.SOFT_ATMOSPHERE,
        intent_field="experience_focus",
    ),
    VisualThinkingSlot(
        key="space",
        label="空间体验",
        caption="组织、动线与场所关系",
        image_type=ArchitectureImageType.SITE_DIAGRAM,
        style_preset=VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
        intent_field="spatial_strategy",
    ),
    VisualThinkingSlot(
        key="material",
        label="材料研究",
        caption="材质触感与建造语汇",
        image_type=ArchitectureImageType.MATERIAL_STUDY,
        style_preset=VisionStylePreset.WATERCOLOR_NOTE,
        intent_field="material_strategy",
    ),
    VisualThinkingSlot(
        key="massing",
        label="体量推演",
        caption="体量、轮廓与形式语言",
        image_type=ArchitectureImageType.CONCEPT_SKETCH,
        style_preset=VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
        intent_field="formal_language",
    ),
)


def slot_by_key(key: str) -> VisualThinkingSlot | None:
    for slot in VISUAL_THINKING_SLOTS:
        if slot.key == key:
            return slot
    return None


def intent_binding_lines(direction: ConceptDirection, slot: VisualThinkingSlot) -> list[str]:
    """Human-readable DesignIntent lines this slot must express."""
    lines: list[str] = []
    theme = (direction.theme or "").strip()
    if theme:
        lines.append(f"主题：{theme}")

    if slot.key == "atmosphere":
        text = (direction.experience_focus or direction.theme or "").strip()
        if text:
            lines.append(f"表达：{text}")
        if direction.spatial_intent is not None:
            light = direction.spatial_intent.light_strategy.strip()
            if light:
                lines.append(f"光策略：{light}")
    elif slot.key == "space":
        text = (
            direction.spatial_strategy.strip()
            or direction.spatial_idea.strip()
        )
        if text:
            lines.append(f"空间策略：{text}")
        if direction.spatial_intent is not None:
            rel = direction.spatial_intent.spatial_relationships.strip()
            move = direction.spatial_intent.movement_experience.strip()
            if rel:
                lines.append(f"空间关系：{rel}")
            if move:
                lines.append(f"动线：{move}")
    elif slot.key == "material":
        text = (direction.material_strategy or "").strip()
        if text:
            lines.append(f"材料策略：{text}")
    elif slot.key == "massing":
        text = (direction.formal_language or "").strip()
        if text:
            lines.append(f"形式语言：{text}")
        for rule in direction.design_rules[:2]:
            formal = rule.formal_translation.strip()
            if formal:
                lines.append(f"规则：{formal}")

    if direction.differentiator.strip() and len(lines) < 4:
        lines.append(f"差异点：{direction.differentiator.strip()}")
    return lines[:5]


def focus_hint_for_slot(direction: ConceptDirection, slot: VisualThinkingSlot) -> str:
    """Compact focus string injected into synthesize / subject."""
    bindings = intent_binding_lines(direction, slot)
    if bindings:
        return "；".join(bindings)[:400]
    return f"{slot.label}：{direction.title}"
