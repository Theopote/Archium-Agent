"""Architecture Style Presets — measurable DesignSystem token overlays.

Distinct from Vision ``VisionStylePreset`` (image generation look). These presets
encode presentation *office aesthetic* plus narrative personality and content
policy (v0.3).
"""

from archium.domain.visual.style.apply import apply_style_preset, design_system_fingerprint
from archium.domain.visual.style.presets import (
    EmotionLevel,
    ImageRole,
    NarrativeLogic,
    PresentationPersonality,
    StyleContentPolicy,
    StylePreset,
    StylePresetId,
    merge_copy_budget_stricter,
)
from archium.domain.visual.style.registry import (
    DEFAULT_STYLE_PRESET_ID,
    get_style_preset,
    list_style_presets,
    resolve_style_preset_id,
)

__all__ = [
    "DEFAULT_STYLE_PRESET_ID",
    "EmotionLevel",
    "ImageRole",
    "NarrativeLogic",
    "PresentationPersonality",
    "StyleContentPolicy",
    "StylePreset",
    "StylePresetId",
    "apply_style_preset",
    "design_system_fingerprint",
    "get_style_preset",
    "list_style_presets",
    "merge_copy_budget_stricter",
    "resolve_style_preset_id",
]
