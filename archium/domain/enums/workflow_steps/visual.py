"""Visual composition workflow steps (DOM-007)."""

from enum import StrEnum


class VisualWorkflowStep(StrEnum):
    VISUAL_LOAD_CONTEXT = "visual_load_context"
    VISUAL_LOAD_DESIGN_SYSTEM = "visual_load_design_system"
    VISUAL_GENERATE_ART_DIRECTION = "visual_generate_art_direction"
    VISUAL_AWAIT_ART_DIRECTION_APPROVAL = "visual_await_art_direction_approval"
    VISUAL_GENERATE_INTENTS = "visual_generate_intents"
    VISUAL_GENERATE_DECK_COMPOSITION = "visual_generate_deck_composition"
    VISUAL_GENERATE_LAYOUT_CANDIDATES = "visual_generate_layout_candidates"
    VISUAL_SELECT_LAYOUTS = "visual_select_layouts"
    VISUAL_VALIDATE_LAYOUTS = "visual_validate_layouts"
    VISUAL_REPAIR_LAYOUTS = "visual_repair_layouts"
    VISUAL_APPLY_SAFE_FALLBACK = "visual_apply_safe_fallback"
    VISUAL_AWAIT_LAYOUT_REVIEW = "visual_await_layout_review"
    VISUAL_RENDER = "visual_render"
    VISUAL_CRITIQUE = "visual_critique"
    VISUAL_SCENE_REPAIR = "visual_scene_repair"
    VISUAL_FINALIZE = "visual_finalize"
