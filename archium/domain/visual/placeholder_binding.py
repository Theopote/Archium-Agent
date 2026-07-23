"""Placeholder binding signatures for real PPTX template fill.

Enterprise templates are often hand-edited, so placeholder *index* alone is
unreliable. Prefer stable semantic role, then type, name, geometry, and only
then index.

Normalization helpers live in
``archium.application.visual.placeholder_binding_normalize`` (DOM-014).
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel

# Match priority (highest first) — documented for QA and callers.
PLACEHOLDER_MATCH_PRIORITY: tuple[str, ...] = (
    "semantic_role",
    "placeholder_type",
    "placeholder_name",
    "geometry",
    "placeholder_idx",
)


class PlaceholderBindingSignature(DomainModel):
    """Durable identity for a PPTX placeholder across hand-edited masters."""

    placeholder_idx: int | None = None
    placeholder_name: str = ""
    placeholder_type: str = ""
    semantic_role: str = ""
    fallback_matchers: list[str] = Field(default_factory=list)


class PlaceholderBindingTarget(DomainModel):
    """What content fill is looking for when resolving a placeholder."""

    semantic_role: str = ""
    preferred_types: list[str] = Field(default_factory=list)
    preferred_names: list[str] = Field(default_factory=list)
    # Optional geometry hint (inches): x, y, width, height.
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    preferred_idx: int | None = None
