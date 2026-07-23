"""Resolve content targets onto template placeholders without relying on index alone."""

from __future__ import annotations

from dataclasses import dataclass

from archium.application.visual.placeholder_binding_normalize import normalize_placeholder_type
from archium.domain.visual.placeholder_binding import (
    PLACEHOLDER_MATCH_PRIORITY,
    PlaceholderBindingSignature,
    PlaceholderBindingTarget,
)
from archium.domain.visual.reference_slide import ReferenceElement


@dataclass(frozen=True)
class PlaceholderMatchResult:
    element: ReferenceElement
    score: float
    matched_by: str


def geometry_similarity(
    *,
    ax: float,
    ay: float,
    aw: float,
    ah: float,
    bx: float,
    by: float,
    bw: float,
    bh: float,
) -> float:
    """IoU-like overlap in [0, 1] for axis-aligned boxes in inches."""
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        # Soft distance fallback when boxes do not overlap.
        acx, acy = ax + aw / 2, ay + ah / 2
        bcx, bcy = bx + bw / 2, by + bh / 2
        dist = ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5
        diag = max((aw**2 + ah**2) ** 0.5, (bw**2 + bh**2) ** 0.5, 0.01)
        return float(max(0.0, 1.0 - dist / diag) * 0.35)
    inter = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return float(inter / union)


def score_placeholder_candidate(
    signature: PlaceholderBindingSignature | None,
    element: ReferenceElement,
    target: PlaceholderBindingTarget,
) -> tuple[float, str]:
    """Score one candidate. Returns (score, primary matched signal)."""
    sig = signature or element.placeholder_binding
    role = ""
    ptype = ""
    name = ""
    idx: int | None = None
    if sig is not None:
        role = (sig.semantic_role or "").strip().casefold()
        ptype = normalize_placeholder_type(sig.placeholder_type)
        name = (sig.placeholder_name or "").strip().casefold()
        idx = sig.placeholder_idx
    if not role:
        role = (element.semantic_role or "").strip().casefold()
    if not name:
        name = (element.source_shape_name or "").strip().casefold()

    target_role = (target.semantic_role or "").strip().casefold()
    score = 0.0
    matched_by = "none"

    # Weights follow PLACEHOLDER_MATCH_PRIORITY.
    if target_role and role and target_role == role:
        score += 40.0
        matched_by = "semantic_role"
    elif target_role and role and target_role in role:
        score += 20.0
        matched_by = "semantic_role"

    preferred_types = {
        normalize_placeholder_type(item) for item in target.preferred_types if item
    }
    if ptype and preferred_types and ptype in preferred_types:
        score += 25.0
        if matched_by == "none":
            matched_by = "placeholder_type"

    preferred_names = {
        item.strip().casefold() for item in target.preferred_names if item.strip()
    }
    if name and preferred_names and name in preferred_names:
        score += 18.0
        if matched_by == "none":
            matched_by = "placeholder_name"
    elif name and preferred_names:
        for preferred in preferred_names:
            if preferred and preferred in name:
                score += 10.0
                if matched_by == "none":
                    matched_by = "placeholder_name"
                break

    if (
        target.x is not None
        and target.y is not None
        and target.width is not None
        and target.height is not None
    ):
        geom = geometry_similarity(
            ax=element.x,
            ay=element.y,
            aw=element.width,
            ah=element.height,
            bx=target.x,
            by=target.y,
            bw=target.width,
            bh=target.height,
        )
        if geom >= 0.35:
            score += 12.0 * geom
            if matched_by == "none":
                matched_by = "geometry"

    if target.preferred_idx is not None and idx is not None and target.preferred_idx == idx:
        score += 5.0
        if matched_by == "none":
            matched_by = "placeholder_idx"

    _ = PLACEHOLDER_MATCH_PRIORITY  # documented contract for callers / tests
    return score, matched_by


def match_placeholder(
    candidates: list[ReferenceElement],
    target: PlaceholderBindingTarget,
    *,
    used_ids: set[str] | None = None,
    min_score: float = 15.0,
) -> PlaceholderMatchResult | None:
    """Pick the best unbound candidate for *target* using signature priority."""
    used = used_ids or set()
    best: PlaceholderMatchResult | None = None
    for element in candidates:
        if element.id in used:
            continue
        score, matched_by = score_placeholder_candidate(
            element.placeholder_binding,
            element,
            target,
        )
        if score < min_score:
            continue
        if best is None or score > best.score:
            best = PlaceholderMatchResult(
                element=element,
                score=score,
                matched_by=matched_by,
            )
    return best


def effective_semantic_role(element: ReferenceElement) -> str:
    """Role used for fill — signature first, then element heuristic."""
    binding = element.placeholder_binding
    if binding is not None and binding.semantic_role.strip():
        role = binding.semantic_role.strip().casefold()
        if role and role != "placeholder":
            return role
    role = (element.semantic_role or "").strip().casefold()
    return role if role and role != "placeholder" else "body"
