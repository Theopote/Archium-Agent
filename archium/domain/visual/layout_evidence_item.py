"""Semantic evidence pairs for layout generators (presentation BC — not IntentEvidence)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from archium.domain._base import DomainModel


class EvidenceItemRole(StrEnum):
    """Hierarchy role for one photo/drawing evidence slot on a page."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"
    DETAIL = "detail"


class LayoutEvidenceItem(DomainModel):
    """One asset bound to its claim for evidence-board layouts.

    Replaces parallel ``supporting_asset_refs[]`` + ``key_points[]`` pairing.
    ``asset`` may be empty at narrative time and hydrated during visual matching.
    """

    claim: str = Field(min_length=1)
    role: EvidenceItemRole = EvidenceItemRole.SUPPORTING
    asset: str | None = None
    focus: str | None = None
    source: str | None = None

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_role(cls, value: object) -> object:
        if value is None or value == "":
            return EvidenceItemRole.SUPPORTING
        if isinstance(value, EvidenceItemRole):
            return value
        return str(value).strip().lower()

    @field_validator("asset", mode="before")
    @classmethod
    def _normalize_asset(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def sort_evidence_items(items: list[LayoutEvidenceItem]) -> list[LayoutEvidenceItem]:
    """Order items primary → supporting → detail (stable within each tier)."""
    order = {
        EvidenceItemRole.PRIMARY: 0,
        EvidenceItemRole.SUPPORTING: 1,
        EvidenceItemRole.DETAIL: 2,
    }
    return sorted(items, key=lambda item: order.get(item.role, 9))


def build_evidence_items_from_claims(
    claims: list[str],
    *,
    source: str | None = None,
) -> list[LayoutEvidenceItem]:
    """Build narrative evidence items before assets are bound."""
    items: list[LayoutEvidenceItem] = []
    for index, claim in enumerate(claims):
        cleaned = claim.strip()
        if not cleaned:
            continue
        if index == 0:
            role = EvidenceItemRole.PRIMARY
        elif index < 3:
            role = EvidenceItemRole.SUPPORTING
        else:
            role = EvidenceItemRole.DETAIL
        items.append(LayoutEvidenceItem(claim=cleaned, role=role, source=source))
    return items


def hydrate_evidence_item_assets(
    items: list[LayoutEvidenceItem],
    *,
    hero_asset_ref: str | None,
    supporting_asset_refs: list[str],
) -> list[LayoutEvidenceItem]:
    """Fill missing ``asset`` refs from visual-intent asset pools."""
    pool: list[str] = []
    if hero_asset_ref:
        pool.append(hero_asset_ref)
    for ref in supporting_asset_refs:
        if ref not in pool:
            pool.append(ref)
    hydrated: list[LayoutEvidenceItem] = []
    pool_index = 0
    for item in items:
        asset = item.asset
        if not asset and pool_index < len(pool):
            asset = pool[pool_index]
            pool_index += 1
        if not asset:
            continue
        hydrated.append(item if item.asset == asset else item.model_copy(update={"asset": asset}))
    return hydrated


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
