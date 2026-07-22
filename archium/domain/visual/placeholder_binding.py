"""Placeholder binding signatures for real PPTX template fill.

Enterprise templates are often hand-edited, so placeholder *index* alone is
unreliable. Prefer stable semantic role, then type, name, geometry, and only
then index.
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

# OOXML / python-pptx placeholder type name → semantic role.
_PLACEHOLDER_TYPE_TO_ROLE: dict[str, str] = {
    "TITLE": "title",
    "CENTER_TITLE": "title",
    "VERTICAL_TITLE": "title",
    "SUBTITLE": "subtitle",
    "BODY": "body",
    "OBJECT": "body",
    "VERTICAL_BODY": "body",
    "PICTURE": "hero_image",
    "BITMAP": "hero_image",
    "CLIP_ART": "supporting_image",
    "CHART": "chart",
    "TABLE": "table",
    "MEDIA_CLIP": "hero_image",
    "ORG_CHART": "diagram",
    "FOOTER": "caption",
    "HEADER": "caption",
    "DATE": "caption",
    "SLIDE_NUMBER": "caption",
}


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


def normalize_placeholder_type(raw: object) -> str:
    """Normalize python-pptx placeholder type / enum / string to UPPER_SNAKE."""
    if raw is None:
        return ""
    name = getattr(raw, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip().upper()
    text = str(raw).strip()
    if not text:
        return ""
    # Values like "TITLE (1)" or "PpPlaceholderType.TITLE"
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    text = text.split("(")[0].strip()
    return text.upper().replace(" ", "_")


def semantic_role_from_placeholder_type(
    placeholder_type: str,
    *,
    hosts_picture: bool = False,
    height: float | None = None,
    page_height: float | None = None,
) -> str:
    """Map native placeholder type onto Archium semantic roles."""
    key = normalize_placeholder_type(placeholder_type)
    if not key and hosts_picture:
        if (
            height is not None
            and page_height is not None
            and page_height > 0
            and height < page_height * 0.45
        ):
            return "supporting_image"
        return "hero_image"
    role = _PLACEHOLDER_TYPE_TO_ROLE.get(key, "")
    if (
        role == "hero_image"
        and height is not None
        and page_height
        and page_height > 0
        and height < page_height * 0.45
    ):
        return "supporting_image"
    return role


def build_fallback_matchers(
    *,
    semantic_role: str,
    placeholder_type: str,
    placeholder_name: str,
    placeholder_idx: int | None,
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[str]:
    """Ordered fallback tokens mirroring PLACEHOLDER_MATCH_PRIORITY."""
    matchers: list[str] = []
    role = semantic_role.strip().lower()
    if role and role != "placeholder":
        matchers.append(f"role:{role}")
    ptype = normalize_placeholder_type(placeholder_type)
    if ptype:
        matchers.append(f"type:{ptype}")
    name = placeholder_name.strip()
    if name:
        matchers.append(f"name:{name.casefold()}")
    matchers.append(
        "geom:"
        f"{round(x, 3)},{round(y, 3)},{round(width, 3)},{round(height, 3)}"
    )
    if placeholder_idx is not None:
        matchers.append(f"idx:{placeholder_idx}")
    return matchers


def build_placeholder_binding_signature(
    *,
    placeholder_idx: int | None,
    placeholder_name: str,
    placeholder_type: str,
    semantic_role: str,
    x: float,
    y: float,
    width: float,
    height: float,
    hosts_picture: bool = False,
    page_height: float | None = None,
) -> PlaceholderBindingSignature:
    ptype = normalize_placeholder_type(placeholder_type)
    role = (semantic_role or "").strip().lower()
    if not role or role == "placeholder":
        role = semantic_role_from_placeholder_type(
            ptype,
            hosts_picture=hosts_picture,
            height=height,
            page_height=page_height,
        ) or role or "body"
    return PlaceholderBindingSignature(
        placeholder_idx=placeholder_idx,
        placeholder_name=(placeholder_name or "").strip(),
        placeholder_type=ptype,
        semantic_role=role,
        fallback_matchers=build_fallback_matchers(
            semantic_role=role,
            placeholder_type=ptype,
            placeholder_name=placeholder_name,
            placeholder_idx=placeholder_idx,
            x=x,
            y=y,
            width=width,
            height=height,
        ),
    )
