"""Shim: placeholder binding normalize lives in domain.visual."""

from archium.domain.visual.placeholder_binding_normalize import (
    build_fallback_matchers,
    build_placeholder_binding_signature,
    normalize_placeholder_type,
    semantic_role_from_placeholder_type,
)

__all__ = [
    "build_fallback_matchers",
    "build_placeholder_binding_signature",
    "normalize_placeholder_type",
    "semantic_role_from_placeholder_type",
]
