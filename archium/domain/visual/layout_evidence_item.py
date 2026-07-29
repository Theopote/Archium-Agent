"""Semantic evidence pairs for layout generators (presentation BC — not IntentEvidence)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceItemRole(StrEnum):
    """Hierarchy role for one photo/drawing evidence slot on a page."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"
    DETAIL = "detail"


@dataclass(frozen=True)
class LayoutEvidenceItem:
    """One asset bound to its claim for evidence-board layouts.

    Replaces parallel ``supporting_asset_refs[]`` + ``key_points[]`` pairing.
    """

    asset: str
    claim: str
    role: EvidenceItemRole = EvidenceItemRole.SUPPORTING
    focus: str | None = None
    source: str | None = None


def sort_evidence_items(items: list[LayoutEvidenceItem]) -> list[LayoutEvidenceItem]:
    """Order items primary → supporting → detail (stable within each tier)."""
    order = {
        EvidenceItemRole.PRIMARY: 0,
        EvidenceItemRole.SUPPORTING: 1,
        EvidenceItemRole.DETAIL: 2,
    }
    return sorted(items, key=lambda item: order.get(item.role, 9))


def build_evidence_items_from_legacy(
    *,
    asset_refs: list[str],
    claims: list[str],
    source: str | None = None,
    hero_asset_ref: str | None = None,
) -> list[LayoutEvidenceItem]:
    """Bridge legacy parallel arrays into semantic evidence items."""
    refs = list(asset_refs)
    if hero_asset_ref and hero_asset_ref not in refs:
        refs = [hero_asset_ref, *refs]
    items: list[LayoutEvidenceItem] = []
    for index, ref in enumerate(refs):
        claim = claims[index] if index < len(claims) else f"问题节点 {index + 1}"
        if index == 0:
            role = EvidenceItemRole.PRIMARY
        elif index < 3:
            role = EvidenceItemRole.SUPPORTING
        else:
            role = EvidenceItemRole.DETAIL
        items.append(
            LayoutEvidenceItem(
                asset=ref,
                claim=claim,
                role=role,
                source=source,
            )
        )
    return items
