"""Scene font helpers with filesystem probing wired to font_resolver."""

from __future__ import annotations

from archium.domain.visual.font_names import (
    CJK_FALLBACK_CHAIN,
    DEFAULT_CJK_FONT,
    DEFAULT_LATIN_FONT,
    LATIN_FALLBACK_CHAIN,
)
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.scene_fonts import (
    ResolvedTextFonts,
    cjk_latin_from_typography,
    collect_font_assets,
    collect_font_assets_from_scene,
    css_font_stack,
    preferred_would_be_latin_only,
    repair_scene_fonts,
    repair_text_node_fonts,
    resolve_text_fonts,
    text_has_cjk,
    text_script,
    typography_role_for_semantic,
)
from archium.domain.visual.scene_fonts import (
    detect_font_fallbacks as _detect_font_fallbacks,
)
from archium.domain.visual.scene_fonts import (
    first_available_family as _first_available_family,
)
from archium.infrastructure.layout.font_resolver import resolve_font_file


def _probe(family: str, bold: bool = False) -> bool:
    return resolve_font_file(family, bold=bold) is not None


def family_file_available(family: str, *, bold: bool = False) -> bool:
    return _probe(family, bold)


def first_available_family(
    preferred: str,
    chain: tuple[str, ...],
    *,
    bold: bool = False,
) -> tuple[str, str | None]:
    return _first_available_family(preferred, chain, bold=bold, probe=_probe)


def detect_font_fallbacks(scene: RenderScene) -> list[str]:
    return _detect_font_fallbacks(scene, probe=_probe)


__all__ = [
    "CJK_FALLBACK_CHAIN",
    "DEFAULT_CJK_FONT",
    "DEFAULT_LATIN_FONT",
    "LATIN_FALLBACK_CHAIN",
    "ResolvedTextFonts",
    "cjk_latin_from_typography",
    "collect_font_assets",
    "collect_font_assets_from_scene",
    "css_font_stack",
    "detect_font_fallbacks",
    "family_file_available",
    "first_available_family",
    "preferred_would_be_latin_only",
    "repair_scene_fonts",
    "repair_text_node_fonts",
    "resolve_text_fonts",
    "text_has_cjk",
    "text_script",
    "typography_role_for_semantic",
]
