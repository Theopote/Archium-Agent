"""Bind semantic ``SlideSpec.evidence_items`` to matched project assets."""

from __future__ import annotations

from uuid import UUID

from archium.application.asset_matching_service import (
    _EVIDENCE_LIKE_VISUALS,
    rank_assets_for_requirement,
)
from archium.domain.asset import Asset
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.slide_asset_binding import SlideAssetBinding, SlideAssetBindingRole
from archium.domain.visual.layout_evidence_item import EvidenceItemRole, LayoutEvidenceItem
from archium.domain.visual_qa import VisualQAReport


def bind_slide_evidence_items(
    slide: SlideSpec,
    assets: list[Asset],
    *,
    assets_by_id: dict[UUID, Asset] | None = None,
    qa_reports: dict[UUID, VisualQAReport] | None = None,
    min_score: float = 0.35,
) -> tuple[SlideSpec, bool]:
    """Fill ``evidence_items[].asset`` from matched requirements or claim scoring."""
    if not slide.evidence_items:
        return slide, False

    known = assets_by_id or {asset.id: asset for asset in assets}
    reports = qa_reports or {}
    requirement_assets = _matched_requirement_asset_ids(slide)
    used: set[UUID] = set()
    updated: list[LayoutEvidenceItem] = []
    changed = False

    for index, item in enumerate(slide.evidence_items):
        existing = _parse_asset_id(item.asset)
        if existing is not None and existing in known:
            used.add(existing)
            updated.append(item)
            continue

        candidate = _candidate_from_requirements(
            item,
            requirement_assets,
            used=used,
            index=index,
        )
        if candidate is None:
            ranked = rank_assets_for_requirement(
                _requirement_for_evidence_item(item, slide),
                [asset for asset in assets if asset.id not in used],
                min_score=min_score,
                qa_reports=reports,
                top_k=1,
            )
            if ranked:
                candidate = ranked[0][0].id

        if candidate is not None and candidate not in used:
            updated.append(item.model_copy(update={"asset": str(candidate)}))
            used.add(candidate)
            changed = True
            continue

        updated.append(item)

    if not changed:
        return slide, False
    return slide.model_copy(update={"evidence_items": updated}), True


def bind_evidence_item_for_asset_binding(
    slide: SlideSpec,
    binding: SlideAssetBinding,
) -> bool:
    """Apply explicit page asset binding onto the next unbound evidence item."""
    if not slide.evidence_items:
        return False
    if binding.binding_role not in {
        SlideAssetBindingRole.PROJECT_PHOTO,
        SlideAssetBindingRole.SUPPORTING_PHOTO,
        SlideAssetBindingRole.REFERENCE_CASE,
    }:
        return False

    target_role = (
        EvidenceItemRole.PRIMARY
        if binding.binding_role == SlideAssetBindingRole.PROJECT_PHOTO
        else EvidenceItemRole.SUPPORTING
    )
    updated: list[LayoutEvidenceItem] = []
    changed = False
    assigned = False
    for item in slide.evidence_items:
        if assigned or item.asset:
            updated.append(item)
            continue
        if item.role == target_role or (
            target_role == EvidenceItemRole.SUPPORTING
            and item.role in {EvidenceItemRole.SUPPORTING, EvidenceItemRole.DETAIL}
        ):
            updated.append(item.model_copy(update={"asset": str(binding.asset_id)}))
            changed = True
            assigned = True
            continue
        updated.append(item)

    if not assigned:
        fallback: list[LayoutEvidenceItem] = []
        for item in slide.evidence_items:
            if not assigned and not item.asset:
                fallback.append(item.model_copy(update={"asset": str(binding.asset_id)}))
                changed = True
                assigned = True
            else:
                fallback.append(item)
        updated = fallback

    if changed:
        slide.evidence_items = updated
    return changed


def ordered_evidence_asset_ids(slide: SlideSpec) -> list[UUID]:
    """Return bound evidence asset ids in narrative order (deduped)."""
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for item in slide.evidence_items:
        asset_id = _parse_asset_id(item.asset)
        if asset_id is None or asset_id in seen:
            continue
        seen.add(asset_id)
        ordered.append(asset_id)
    return ordered


def _matched_requirement_asset_ids(slide: SlideSpec) -> list[UUID]:
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for requirement in slide.visual_requirements:
        asset_id = requirement.primary_asset_id
        if asset_id is None or asset_id in seen:
            continue
        seen.add(asset_id)
        ordered.append(asset_id)
    return ordered


def _candidate_from_requirements(
    item: LayoutEvidenceItem,
    requirement_assets: list[UUID],
    *,
    used: set[UUID],
    index: int,
) -> UUID | None:
    if index < len(requirement_assets):
        candidate = requirement_assets[index]
        if candidate not in used:
            return candidate
    if item.role == EvidenceItemRole.PRIMARY:
        for candidate in requirement_assets:
            if candidate not in used:
                return candidate
    for candidate in requirement_assets:
        if candidate not in used:
            return candidate
    return None


def _requirement_for_evidence_item(
    item: LayoutEvidenceItem,
    slide: SlideSpec,
) -> VisualRequirement:
    visual_type = VisualType.SITE_PHOTO
    for requirement in slide.visual_requirements:
        if requirement.type in _EVIDENCE_LIKE_VISUALS:
            visual_type = requirement.type
            break
    description = item.claim.strip()
    if item.focus and item.focus.strip():
        description = f"{description} {item.focus.strip()}"
    return VisualRequirement(type=visual_type, description=description, required=True)


def _parse_asset_id(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value).strip())
    except ValueError:
        return None
