"""Architectural symbol library — linear / diagram symbols, not emoji icons."""

from __future__ import annotations

from enum import StrEnum


class ArchitecturalSymbolId(StrEnum):
    """Minimal v1 catalog — circulation / axis, not 🚗 trees."""

    CIRCULATION_FLOW = "circulation_flow"
    AXIS = "axis"
    ENTRANCE = "entrance"
    NODE = "node"
    GREEN_NETWORK = "green_network"


# Glyph / text stand-ins until SVG pack is wired (Render may use text or shape).
SYMBOL_GLYPHS: dict[ArchitecturalSymbolId, str] = {
    ArchitecturalSymbolId.CIRCULATION_FLOW: "→ → →",
    ArchitecturalSymbolId.AXIS: "丨",
    ArchitecturalSymbolId.ENTRANCE: "▷",
    ArchitecturalSymbolId.NODE: "●",
    ArchitecturalSymbolId.GREEN_NETWORK: "⑂",
}
