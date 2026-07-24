"""Shim: visual grammar asset helpers live in domain.visual."""

from archium.domain.visual.visual_grammar_assets import (
    BINDING_ROLE_TO_GRAMMAR_SLOTS,
    HERO_GRAMMAR_ROLES,
    find_requirement_for_grammar_slot,
    format_grammar_requirement_description,
    grammar_asset_match_bonus,
    grammar_role_from_requirement,
    preferred_grammar_slots_for_binding,
    resolve_grammar_hero_asset_id,
    visual_types_compatible,
)

__all__ = [
    "BINDING_ROLE_TO_GRAMMAR_SLOTS",
    "HERO_GRAMMAR_ROLES",
    "find_requirement_for_grammar_slot",
    "format_grammar_requirement_description",
    "grammar_asset_match_bonus",
    "grammar_role_from_requirement",
    "preferred_grammar_slots_for_binding",
    "resolve_grammar_hero_asset_id",
    "visual_types_compatible",
]
