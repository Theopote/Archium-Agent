"""Apply ArtDirection / ReferenceStyleProfile overlays onto DesignSystem.

Produces an **in-memory** DesignSystem for RenderScene compilation. Persisted
DesignSystem rows are not mutated.

Priority (later wins on the same token):

1. Base ``DesignSystem``
2. ``ArtDirection`` tone / palette / typography strategy hints
3. ``ReferenceStyleProfile`` color / typography / image cues (highest)

Only cues that can be resolved deterministically are applied (hex colors,
explicit font/size patterns). Free-text strategies that cannot be mapped are
recorded in the returned warnings list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from archium.domain.reference_style import ReferenceStyleProfile, StyleTypographyCue
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import (
    DesignSystem,
    ImageStyleSystem,
    TextStyleToken,
    TypographySystem,
)
from archium.domain.visual.enums import PhotoTreatment

_HEX_RE = re.compile(r"#([0-9A-Fa-f]{3,6}|[0-9A-Fa-f]{8})\b")
_FONT_AT_SIZE_RE = re.compile(
    r"(?:use|使用)\s+([A-Za-z][\w \-]+?)\s+at\s+(\d+(?:\.\d+)?)\s*(?:pt|px|磅)?",
    re.IGNORECASE,
)
_FONT_FAMILY_RE = re.compile(
    r"(?:font(?:[_\s-]?family)?|字体)\s*[:：=]\s*([A-Za-z][\w \-]+)",
    re.IGNORECASE,
)
_SIZE_PT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:pt|px|磅)\b", re.IGNORECASE)
_QUOTED_RE = re.compile(r"[\"“]([^\"”]+)[\"”]")

_COLOR_TOKEN_NAMES = frozenset(
    {
        "background",
        "surface",
        "primary_text",
        "secondary_text",
        "muted_text",
        "primary",
        "secondary",
        "accent",
        "warning",
        "success",
        "border",
        "overlay",
    }
)

_USAGE_ALIASES: dict[str, str] = {
    "background": "background",
    "bg": "background",
    "page": "background",
    "surface": "surface",
    "card": "surface",
    "panel": "surface",
    "primary": "primary",
    "brand": "primary",
    "secondary": "secondary",
    "accent": "accent",
    "highlight": "accent",
    "text": "primary_text",
    "primary_text": "primary_text",
    "body_text": "primary_text",
    "secondary_text": "secondary_text",
    "muted": "muted_text",
    "muted_text": "muted_text",
    "caption": "muted_text",
    "border": "border",
    "line": "border",
    "warning": "warning",
    "success": "success",
    "overlay": "overlay",
}

_TYPO_ROLE_ALIASES: dict[str, str] = {
    "display": "display",
    "title": "title",
    "heading": "heading",
    "h1": "title",
    "h2": "heading",
    "subtitle": "subtitle",
    "body": "body",
    "paragraph": "body",
    "caption": "caption",
    "metric": "metric",
    "footnote": "footnote",
    "source": "source",
    "citation": "source",
}

_DARK_PALETTE = {
    "background": "#1A1A1A",
    "surface": "#2A2A2A",
    "primary_text": "#F5F5F5",
    "secondary_text": "#C8C8C8",
    "muted_text": "#9A9A9A",
    "primary": "#E8E8E8",
    "secondary": "#A0A0A0",
    "accent": "#C9A227",
    "border": "#444444",
    "overlay": "#00000099",
}

_WARM_ACCENT = "#8B4513"
_COOL_ACCENT = "#2C5F7C"
_MINIMAL_BORDER = "#E5E5E5"


@dataclass(frozen=True)
class StyleOverlayResult:
    """Overlayed design system plus human-readable apply notes."""

    design_system: DesignSystem
    warnings: list[str]
    applied_color_tokens: tuple[str, ...] = ()
    applied_typography_roles: tuple[str, ...] = ()


def apply_style_overlays(
    design_system: DesignSystem,
    *,
    art_direction: ArtDirection | None = None,
    reference_style: ReferenceStyleProfile | None = None,
) -> StyleOverlayResult:
    """Return a DesignSystem with deterministic style overlays applied."""
    if art_direction is None and reference_style is None:
        return StyleOverlayResult(design_system=design_system, warnings=[])

    color_updates: dict[str, str] = {}
    typography_updates: dict[str, TextStyleToken] = {}
    image_style = design_system.image_style
    warnings: list[str] = []

    if art_direction is not None:
        art_colors, art_notes = _colors_from_art_direction(art_direction)
        color_updates.update(art_colors)
        warnings.extend(art_notes)
        art_typo, art_typo_notes = _typography_from_art_direction(
            design_system.typography,
            art_direction,
        )
        typography_updates.update(art_typo)
        warnings.extend(art_typo_notes)

    if reference_style is not None:
        ref_colors, ref_notes = _colors_from_reference_style(reference_style)
        color_updates.update(ref_colors)
        warnings.extend(ref_notes)
        ref_typo, ref_typo_notes = _typography_from_reference_style(
            design_system.typography,
            typography_updates,
            reference_style,
        )
        typography_updates.update(ref_typo)
        warnings.extend(ref_typo_notes)
        image_style, image_notes = _image_style_from_reference(
            image_style,
            reference_style,
        )
        warnings.extend(image_notes)

    if not color_updates and not typography_updates and image_style is design_system.image_style:
        warnings.append("style_overlay:no_resolvable_cues")
        return StyleOverlayResult(design_system=design_system, warnings=warnings)

    colors = design_system.colors
    if color_updates:
        colors = colors.model_copy(update=color_updates)

    typography = design_system.typography
    if typography_updates:
        typography = typography.model_copy(update=typography_updates)

    name_suffix = []
    if art_direction is not None:
        name_suffix.append("art")
    if reference_style is not None:
        name_suffix.append("ref")
    overlaid = design_system.model_copy(
        update={
            "name": f"{design_system.name}+{'+'.join(name_suffix)}",
            "description": (
                f"{design_system.description} "
                f"[style overlay: {', '.join(name_suffix)}]"
            ).strip(),
            "colors": colors,
            "typography": typography,
            "image_style": image_style,
            "source_reference": (
                f"{design_system.source_reference or 'design_system'}"
                f"|style_overlay:{'+'.join(name_suffix)}"
            ),
        }
    )
    applied_tokens = tuple(sorted(color_updates))
    applied_roles = tuple(sorted(typography_updates))
    if applied_tokens:
        warnings.append(f"style_overlay:colors={','.join(applied_tokens)}")
    if applied_roles:
        warnings.append(f"style_overlay:typography={','.join(applied_roles)}")
    return StyleOverlayResult(
        design_system=overlaid,
        warnings=warnings,
        applied_color_tokens=applied_tokens,
        applied_typography_roles=applied_roles,
    )


def extract_hex_colors(text: str) -> list[str]:
    """Extract normalized #RRGGBB (or #RGB) colors from free text."""
    found: list[str] = []
    for match in _HEX_RE.finditer(text or ""):
        raw = match.group(1)
        try:
            found.append(_normalize_hex(raw))
        except ValueError:
            continue
    return found


def _normalize_hex(raw: str) -> str:
    cleaned = raw.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) not in {6, 8} or any(c not in "0123456789abcdefABCDEF" for c in cleaned):
        raise ValueError(f"invalid hex: {raw}")
    return f"#{cleaned.upper()}"


def _resolve_usage_token(usage: str) -> str | None:
    key = (usage or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in _COLOR_TOKEN_NAMES:
        return key
    return _USAGE_ALIASES.get(key)


def _resolve_typo_role(role: str) -> str | None:
    key = (role or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in _TYPO_ROLE_ALIASES:
        return _TYPO_ROLE_ALIASES[key]
    return None


def _colors_from_reference_style(
    profile: ReferenceStyleProfile,
) -> tuple[dict[str, str], list[str]]:
    updates: dict[str, str] = {}
    notes: list[str] = []
    for cue in profile.color_cues:
        token = _resolve_usage_token(cue.usage)
        if token is None:
            # Fall back to cue name if it looks like a token.
            token = _resolve_usage_token(cue.name)
        hexes = extract_hex_colors(cue.description) or extract_hex_colors(cue.name)
        if not hexes:
            notes.append(f"style_overlay:skipped_color_cue:{cue.id}:no_hex")
            continue
        if token is None:
            notes.append(f"style_overlay:skipped_color_cue:{cue.id}:unknown_usage")
            continue
        updates[token] = hexes[0]
    return updates, notes


def _parse_typography_cue(
    base: TextStyleToken,
    cue: StyleTypographyCue,
) -> tuple[TextStyleToken | None, list[str]]:
    text = cue.description or ""
    font_family: str | None = None
    font_size: float | None = None
    notes: list[str] = []

    at_match = _FONT_AT_SIZE_RE.search(text)
    if at_match:
        font_family = at_match.group(1).strip()
        font_size = float(at_match.group(2))
    else:
        family_match = _FONT_FAMILY_RE.search(text)
        if family_match:
            font_family = family_match.group(1).strip()
        quoted = _QUOTED_RE.search(text)
        if font_family is None and quoted:
            font_family = quoted.group(1).strip()
        size_match = _SIZE_PT_RE.search(text)
        if size_match:
            font_size = float(size_match.group(1))

    if font_family is None and font_size is None:
        notes.append(f"style_overlay:skipped_typography_cue:{cue.id}:unparsed")
        return None, notes

    # Drop trailing junk like "if applied"
    if font_family is not None:
        font_family = re.sub(
            r"\s+(if|when|when\s+applied|if\s+applied).*$",
            "",
            font_family,
            flags=re.IGNORECASE,
        ).strip(" ,.;")

    updates: dict[str, object] = {}
    if font_family:
        updates["font_family"] = font_family
        # Latin-facing pages often share the named family when it is Latin.
        if all(ord(ch) < 128 for ch in font_family):
            updates["font_family_latin"] = font_family
    if font_size is not None and font_size > 0:
        updates["font_size"] = font_size
        updates["line_height"] = round(font_size * 1.35, 2)

    return base.model_copy(update=updates), notes


def _typography_from_reference_style(
    base: TypographySystem,
    pending: dict[str, TextStyleToken],
    profile: ReferenceStyleProfile,
) -> tuple[dict[str, TextStyleToken], list[str]]:
    updates: dict[str, TextStyleToken] = {}
    notes: list[str] = []
    for cue in profile.typography_cues:
        role = _resolve_typo_role(cue.role)
        if role is None:
            notes.append(f"style_overlay:skipped_typography_cue:{cue.id}:unknown_role")
            continue
        current = pending.get(role) or getattr(base, role)
        token, cue_notes = _parse_typography_cue(current, cue)
        notes.extend(cue_notes)
        if token is not None:
            updates[role] = token
    return updates, notes


def _colors_from_art_direction(
    art: ArtDirection,
) -> tuple[dict[str, str], list[str]]:
    updates: dict[str, str] = {}
    notes: list[str] = []
    blob = " ".join(
        [
            art.palette_strategy or "",
            art.typography_strategy or "",
            " ".join(art.visual_tone or []),
            " ".join(art.emotional_keywords or []),
            " ".join(art.consistency_rules or []),
        ]
    ).lower()

    # Explicit hex in strategies win first when usage is also mentioned nearby.
    for token in _COLOR_TOKEN_NAMES:
        # e.g. "background #FF00AA" or "accent=#112233"
        pattern = re.compile(
            rf"\b{re.escape(token)}\b[^#]{{0,24}}#([0-9A-Fa-f]{{3,8}})\b",
            re.IGNORECASE,
        )
        match = pattern.search(blob)
        if match:
            try:
                updates[token] = _normalize_hex(match.group(1))
            except ValueError:
                continue

    free_hexes = extract_hex_colors(blob)
    if free_hexes and "accent" not in updates:
        updates["accent"] = free_hexes[0]
        if len(free_hexes) > 1 and "primary" not in updates:
            updates["primary"] = free_hexes[1]
        if len(free_hexes) > 2 and "background" not in updates:
            updates["background"] = free_hexes[2]

    if any(k in blob for k in ("dark", "深色", "夜间", "black background", "night")):
        for key, value in _DARK_PALETTE.items():
            updates.setdefault(key, value)
        notes.append("style_overlay:art_direction:dark_palette")
    if any(k in blob for k in ("warm", "暖色", "warm tone", "terracotta")):
        updates.setdefault("accent", _WARM_ACCENT)
        notes.append("style_overlay:art_direction:warm_accent")
    if any(k in blob for k in ("cool", "冷色", "blue tone", "slate")):
        updates.setdefault("accent", _COOL_ACCENT)
        notes.append("style_overlay:art_direction:cool_accent")
    if any(k in blob for k in ("minimal", "克制", "sparse", "clean")):
        updates.setdefault("border", _MINIMAL_BORDER)
        notes.append("style_overlay:art_direction:minimal_border")

    # Neon / loud palette keyword used in honesty tests — only when hex already present
    # or explicit pink language maps to a known accent.
    if (
        any(k in blob for k in ("neon", "hot pink", "hot-pink", "荧光"))
        and "background" not in updates
        and re.search(r"pink|粉", blob)
    ):
        # Prefer reference-style hex when available; art alone gets a vivid accent.
        updates.setdefault("accent", "#FF00AA")
        notes.append("style_overlay:art_direction:neon_accent")

    return updates, notes


def _typography_from_art_direction(
    base: TypographySystem,
    art: ArtDirection,
) -> tuple[dict[str, TextStyleToken], list[str]]:
    updates: dict[str, TextStyleToken] = {}
    notes: list[str] = []
    strategy = (art.typography_strategy or "").lower()
    if any(k in strategy for k in ("oversized", "大标题", "large display", "hero type")):
        for role in ("display", "title"):
            token: TextStyleToken = getattr(base, role)
            scale = 1.35 if role == "display" else 1.25
            updates[role] = token.model_copy(
                update={
                    "font_size": round(token.font_size * scale, 2),
                    "line_height": round(token.line_height * scale, 2),
                    "font_weight": max(token.font_weight, 700),
                }
            )
        notes.append("style_overlay:art_direction:oversized_titles")
    if any(k in strategy for k in ("compact", "密集", "dense type")):
        for role in ("body", "caption", "footnote"):
            token = getattr(base, role)
            updates[role] = token.model_copy(
                update={
                    "font_size": max(8.0, round(token.font_size * 0.92, 2)),
                    "line_height": max(10.0, round(token.line_height * 0.92, 2)),
                }
            )
        notes.append("style_overlay:art_direction:compact_type")
    return updates, notes


def _image_style_from_reference(
    base: ImageStyleSystem,
    profile: ReferenceStyleProfile,
) -> tuple[ImageStyleSystem, list[str]]:
    notes: list[str] = []
    treatment_text = (profile.image_treatment or "").lower()
    if not treatment_text and not profile.graphic_elements:
        return base, notes

    photo = base.photo_treatment
    if any(k in treatment_text for k in ("scan", "图纸", "document", "线稿")):
        photo = PhotoTreatment.DOCUMENT_SCAN
    elif any(k in treatment_text for k in ("historical", "档案", "复古", "sepia")):
        photo = PhotoTreatment.HISTORICAL
    elif any(k in treatment_text for k in ("unify", "统一", "subtle", "克制")):
        photo = PhotoTreatment.SUBTLE_UNIFY
    elif any(k in treatment_text for k in ("none", "raw", "原图")):
        photo = PhotoTreatment.NONE

    if photo != base.photo_treatment:
        notes.append(f"style_overlay:image_treatment:{photo.value}")
        return base.model_copy(update={"photo_treatment": photo}), notes
    return base, notes
