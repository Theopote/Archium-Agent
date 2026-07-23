"""Architectural icon registry — semantic names map to bundled SVG assets.

Models output semantic keys (e.g. ``pedestrian_flow``); a local matcher selects
the concrete SVG. Icons are not project Assets and must not be LLM filenames.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel


class ArchitecturalIcon(DomainModel):
    """One curated pictogram for architectural presentation use."""

    id: str = Field(min_length=1, max_length=100)
    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    folder: str = ""  # architecture | environment | traffic | energy | culture
    svg_path: str = Field(min_length=1)  # pack-relative path under assets/icons
    embedding: list[float] = Field(default_factory=list)
    license: str = Field(default="MIT", min_length=1)
    description: str = ""


class ArchitecturalIconMatch(DomainModel):
    """Result of matching a semantic query onto the registry."""

    icon: ArchitecturalIcon
    score: float = Field(ge=0.0, le=1.0)
    matched_by: str = Field(min_length=1)  # exact_alias | alias | category | embedding
