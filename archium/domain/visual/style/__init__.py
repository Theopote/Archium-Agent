"""Architecture Style Presets — measurable DesignSystem token overlays.

Distinct from Vision ``VisionStylePreset`` (image generation look). These presets
encode presentation *office aesthetic* (minimal / technical / luxury / …).
"""

from archium.domain.visual.style.apply import apply_style_preset, design_system_fingerprint
from archium.domain.visual.style.presets import StylePreset, StylePresetId
from archium.domain.visual.style.registry import (
    DEFAULT_STYLE_PRESET_ID,
    get_style_preset,
    list_style_presets,
    resolve_style_preset_id,
)

__all__ = [
    "DEFAULT_STYLE_PRESET_ID",
    "StylePreset",
    "StylePresetId",
    "apply_style_preset",
    "design_system_fingerprint",
    "get_style_preset",
    "list_style_presets",
    "resolve_style_preset_id",
]
