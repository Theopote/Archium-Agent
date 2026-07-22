"""Shared RenderScene font policy — CJK defaults, fallback chains, asset collection.

HTML / PNG / PPTX / Canvas must use the same resolution rules so Chinese text
never silently sits on Latin-only families (e.g. Arial) without recording a
fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from archium.domain.visual.design_system import DesignSystem, TypographySystem
from archium.domain.visual.render_scene import FontAsset, RenderNode, RenderScene, TextNode
from archium.infrastructure.layout.font_resolver import (
    CJK_FALLBACK_CHAIN,
    DEFAULT_CJK_FONT,
    DEFAULT_LATIN_FONT,
    LATIN_FALLBACK_CHAIN,
    resolve_font_file,
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")

_TYPOGRAPHY_ROLES: tuple[str, ...] = (
    "display",
    "title",
    "subtitle",
    "heading",
    "body",
    "caption",
    "metric",
    "footnote",
    "source",
)

_ROLE_ALIASES: dict[str, str] = {
    "title": "title",
    "subtitle": "subtitle",
    "caption": "caption",
    "source": "source",
    "citation": "source",
    "metric": "metric",
    "body_text": "body",
    "lead_statement": "body",
    "page_number": "footnote",
    "heading": "heading",
    "display": "display",
    "footnote": "footnote",
}


@dataclass(frozen=True)
class ResolvedTextFonts:
    """Resolved families for one text node."""

    primary: str
    cjk: str
    latin: str
    script: str  # "cjk" | "latin" | "mixed"
    substitutions: tuple[str, ...] = ()


def text_has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def text_script(text: str) -> str:
    has_cjk = text_has_cjk(text)
    has_latin = bool(re.search(r"[A-Za-z]", text or ""))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "cjk"
    return "latin"


def family_file_available(family: str, *, bold: bool = False) -> bool:
    return resolve_font_file(family, bold=bold) is not None


def first_available_family(
    preferred: str,
    chain: tuple[str, ...],
    *,
    bold: bool = False,
) -> tuple[str, str | None]:
    """Return (resolved_family, substitution_note_or_none)."""
    ordered = (preferred, *(f for f in chain if f != preferred))
    if family_file_available(preferred, bold=bold):
        return preferred, None
    for candidate in ordered[1:]:
        if family_file_available(candidate, bold=bold):
            return candidate, f"{preferred}→{candidate} (font file unavailable)"
    # Keep preferred even if missing — OS may still substitute at render time.
    return preferred, f"{preferred}→(unresolved) (font file unavailable)"


def css_font_stack(*, primary: str, cjk: str, latin: str) -> str:
    """CSS font-family list shared by HTML / Canvas preview."""
    seen: list[str] = []
    for name in (primary, cjk, *CJK_FALLBACK_CHAIN, latin, *LATIN_FALLBACK_CHAIN, "sans-serif"):
        if name and name not in seen:
            seen.append(name)
    parts: list[str] = []
    for name in seen:
        if name == "sans-serif":
            parts.append(name)
        else:
            parts.append(f'"{name}"')
    return ", ".join(parts)


def resolve_text_fonts(
    text: str,
    *,
    cjk_family: str | None,
    latin_family: str | None,
    bold: bool = False,
) -> ResolvedTextFonts:
    """Pick portable primary + script families (policy resolution, not OS probe).

    Machine file availability is recorded later via ``detect_font_fallbacks``.
    """
    del bold  # reserved for future weight-specific family maps
    cjk = (cjk_family or "").strip() or DEFAULT_CJK_FONT
    latin = (latin_family or "").strip() or DEFAULT_LATIN_FONT
    script = text_script(text)
    primary = cjk if script in {"cjk", "mixed"} else latin
    return ResolvedTextFonts(
        primary=primary,
        cjk=cjk,
        latin=latin,
        script=script,
        substitutions=(),
    )


def preferred_would_be_latin_only(*, cjk: str, latin: str) -> bool:
    return bool(latin) and latin != cjk


def typography_role_for_semantic(semantic_role: str) -> str:
    return _ROLE_ALIASES.get(semantic_role, "body")


def cjk_latin_from_typography(
    typography: TypographySystem,
    role: str,
) -> tuple[str, str]:
    token = getattr(typography, role, None) or typography.body
    cjk = token.font_family or DEFAULT_CJK_FONT
    latin = token.font_family_latin or DEFAULT_LATIN_FONT
    return cjk, latin


def collect_font_assets(
    design_system: DesignSystem,
    nodes: list[TextNode],
) -> list[FontAsset]:
    """Collect font assets for every typography role and every node family used."""
    assets: list[FontAsset] = []
    seen: set[tuple[str, str, int]] = set()

    def _add(
        *,
        family: str,
        resolved: str,
        role: str,
        script: str,
        weight: int = 400,
    ) -> None:
        key = (resolved, role, weight)
        if key in seen or not family:
            return
        seen.add(key)
        assets.append(
            FontAsset(
                family=family,
                resolved_family=resolved,
                path=None,
                weight=weight,
                style="normal",
                role=role,
                script=script,
            )
        )

    for role in _TYPOGRAPHY_ROLES:
        token = getattr(design_system.typography, role)
        cjk = token.font_family or DEFAULT_CJK_FONT
        latin = token.font_family_latin or DEFAULT_LATIN_FONT
        _add(family=cjk, resolved=cjk, role=role, script="cjk", weight=token.font_weight)
        _add(
            family=latin,
            resolved=latin,
            role=role,
            script="latin",
            weight=token.font_weight,
        )

    for node in nodes:
        role = typography_role_for_semantic(node.semantic_role or "body")
        script = text_script(node.text)
        _add(
            family=node.font_family,
            resolved=node.font_family,
            role=role,
            script=script,
            weight=node.font_weight,
        )
        if node.font_family_cjk:
            _add(
                family=node.font_family_cjk,
                resolved=node.font_family_cjk,
                role=role,
                script="cjk",
                weight=node.font_weight,
            )
        if node.font_family_latin:
            _add(
                family=node.font_family_latin,
                resolved=node.font_family_latin,
                role=role,
                script="latin",
                weight=node.font_weight,
            )

    return assets


def detect_font_fallbacks(scene: RenderScene) -> list[str]:
    """Record real substitutions (CJK-on-Latin, missing files) for manifests."""
    notes: list[str] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        cjk = node.font_family_cjk or DEFAULT_CJK_FONT
        latin = node.font_family_latin or DEFAULT_LATIN_FONT
        bold = node.font_weight >= 600
        # Legacy / bad compile: Latin primary on CJK text.
        if text_has_cjk(node.text) and node.font_family == latin and latin != cjk:
            note = f"{latin}→{cjk} (CJK text; Latin family lacks CJK glyphs)"
            if note not in notes:
                notes.append(note)
        chain = CJK_FALLBACK_CHAIN if text_has_cjk(node.text) else LATIN_FALLBACK_CHAIN
        _family, sub = first_available_family(node.font_family or cjk, chain, bold=bold)
        if sub and sub not in notes:
            notes.append(sub)
        if node.font_family_cjk:
            _cjk, cjk_sub = first_available_family(node.font_family_cjk, CJK_FALLBACK_CHAIN, bold=bold)
            if cjk_sub and cjk_sub not in notes:
                notes.append(cjk_sub)
            _ = _cjk
        _ = _family
    for asset in scene.font_assets:
        family = asset.resolved_family or asset.family
        if not family:
            continue
        chain = CJK_FALLBACK_CHAIN if asset.script == "cjk" else LATIN_FALLBACK_CHAIN
        _resolved, sub = first_available_family(family, chain, bold=asset.weight >= 600)
        if sub and sub not in notes:
            notes.append(sub)
        _ = _resolved
    return notes


def repair_text_node_fonts(scene: RenderScene) -> RenderScene:
    """Rewrite TextNode families to resolved CJK/Latin (for legacy Arial-on-CJK scenes)."""
    nodes: list[RenderNode] = []
    for node in scene.nodes:
        if not isinstance(node, TextNode):
            nodes.append(node)
            continue
        role = typography_role_for_semantic(node.semantic_role or "body")
        token = scene.theme_tokens.typography.get(role, {})
        cjk = node.font_family_cjk
        latin = node.font_family_latin
        if isinstance(token, dict):
            cjk = cjk or str(token.get("font_family") or DEFAULT_CJK_FONT)
            latin = latin or str(token.get("font_family_latin") or DEFAULT_LATIN_FONT)
        cjk = cjk or DEFAULT_CJK_FONT
        latin = latin or DEFAULT_LATIN_FONT
        resolved = resolve_text_fonts(
            node.text,
            cjk_family=cjk,
            latin_family=latin,
            bold=node.font_weight >= 600,
        )
        nodes.append(
            node.model_copy(
                update={
                    "font_family": resolved.primary,
                    "font_family_cjk": resolved.cjk,
                    "font_family_latin": resolved.latin,
                }
            )
        )
    return scene.model_copy(update={"nodes": nodes})


def collect_font_assets_from_scene(scene: RenderScene) -> list[FontAsset]:
    """Rebuild font_assets from theme tokens + text nodes (no DesignSystem needed)."""
    assets: list[FontAsset] = []
    seen: set[tuple[str, str, int]] = set()

    def _add(*, family: str, role: str, script: str, weight: int = 400) -> None:
        key = (family, role, weight)
        if key in seen or not family:
            return
        seen.add(key)
        assets.append(
            FontAsset(
                family=family,
                resolved_family=family,
                path=None,
                weight=weight,
                style="normal",
                role=role,
                script=script,
            )
        )

    for role in _TYPOGRAPHY_ROLES:
        token = scene.theme_tokens.typography.get(role, {})
        if not isinstance(token, dict):
            continue
        cjk = str(token.get("font_family") or DEFAULT_CJK_FONT)
        latin = str(token.get("font_family_latin") or DEFAULT_LATIN_FONT)
        weight = int(str(token.get("font_weight") or 400))
        _add(family=cjk, role=role, script="cjk", weight=weight)
        _add(family=latin, role=role, script="latin", weight=weight)

    for node in scene.nodes:
        if not isinstance(node, TextNode):
            continue
        role = typography_role_for_semantic(node.semantic_role or "body")
        _add(
            family=node.font_family,
            role=role,
            script=text_script(node.text),
            weight=node.font_weight,
        )
        if node.font_family_cjk:
            _add(
                family=node.font_family_cjk,
                role=role,
                script="cjk",
                weight=node.font_weight,
            )
        if node.font_family_latin:
            _add(
                family=node.font_family_latin,
                role=role,
                script="latin",
                weight=node.font_weight,
            )
    return assets


def repair_scene_fonts(scene: RenderScene) -> RenderScene:
    """Fix legacy Latin-on-CJK nodes and refresh font_assets."""
    repaired = repair_text_node_fonts(scene)
    return repaired.model_copy(update={"font_assets": collect_font_assets_from_scene(repaired)})
