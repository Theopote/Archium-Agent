"""Match project assets to slide visual requirements."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_visual_utils import infer_visual_processing_flags
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import AssetRepository, PresentationRepository

_VISUAL_ASSET_TYPES: dict[VisualType, set[AssetType]] = {
    VisualType.SITE_PLAN: {AssetType.DRAWING, AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.FLOOR_PLAN: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.SECTION: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.ELEVATION: {AssetType.DRAWING, AssetType.DIAGRAM},
    VisualType.RENDERING: {AssetType.IMAGE, AssetType.PHOTO},
    VisualType.SITE_PHOTO: {AssetType.PHOTO, AssetType.IMAGE},
    VisualType.DIAGRAM: {AssetType.DIAGRAM, AssetType.DRAWING},
    VisualType.CHART: {AssetType.CHART, AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.TABLE: {AssetType.IMAGE, AssetType.OTHER},
    VisualType.TIMELINE: {AssetType.DIAGRAM, AssetType.IMAGE},
    VisualType.COMPARISON: {AssetType.IMAGE, AssetType.DIAGRAM},
    VisualType.REFERENCE_CASE: {AssetType.IMAGE, AssetType.PHOTO},
    VisualType.ICON: {AssetType.IMAGE, AssetType.OTHER},
    VisualType.MAP: {AssetType.IMAGE, AssetType.DIAGRAM},
    VisualType.TEXT_ONLY: set(),
}


def _tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ")
    return {part for part in normalized.replace("，", " ").replace("。", " ").split() if len(part) > 1}


def score_asset_for_requirement(requirement: VisualRequirement, asset: Asset) -> float:
    """Score how well an asset satisfies a visual requirement."""
    if requirement.type == VisualType.TEXT_ONLY:
        return 0.0

    score = 0.0
    preferred_types = _VISUAL_ASSET_TYPES.get(requirement.type, {AssetType.IMAGE, AssetType.DRAWING})
    if asset.asset_type in preferred_types:
        score += 0.45

    requirement_tokens = _tokenize(requirement.type.value) | _tokenize(requirement.description)
    asset_tokens = _tokenize(asset.filename)
    if asset.description:
        asset_tokens |= _tokenize(asset.description)
    asset_tokens |= set(asset.tags)

    overlap = requirement_tokens & asset_tokens
    if overlap:
        score += min(0.35, 0.1 * len(overlap))

    if asset.quality_score is not None:
        score += 0.2 * asset.quality_score

    if asset.is_low_resolution:
        score -= 0.15

    return max(score, 0.0)


def rank_assets_for_requirement(
    requirement: VisualRequirement,
    assets: list[Asset],
    *,
    min_score: float = 0.35,
    top_k: int = 3,
) -> list[tuple[Asset, float]]:
    ranked = sorted(
        ((asset, score_asset_for_requirement(requirement, asset)) for asset in assets),
        key=lambda item: item[1],
        reverse=True,
    )
    return [(asset, score) for asset, score in ranked if score >= min_score][:top_k]


def apply_asset_match(
    requirement: VisualRequirement,
    ranked: list[tuple[Asset, float]],
    *,
    overwrite: bool = False,
) -> bool:
    """Apply ranked matches to a requirement. Returns True if changed."""
    infer_visual_processing_flags(requirement)
    requirement.candidate_asset_ids = [asset.id for asset, _score in ranked]

    if requirement.confirmed and not overwrite:
        if requirement.preferred_asset_ids:
            return bool(requirement.candidate_asset_ids)
        return False

    if requirement.type == VisualType.TEXT_ONLY:
        return False

    if not ranked:
        if overwrite and not requirement.confirmed:
            requirement.preferred_asset_ids = []
            requirement.match_score = None
            return True
        return bool(requirement.candidate_asset_ids)

    best_asset, best_score = ranked[0]
    if requirement.preferred_asset_ids and not overwrite:
        return bool(requirement.candidate_asset_ids)

    requirement.preferred_asset_ids = [best_asset.id]
    requirement.match_score = best_score
    return True


class AssetMatchingService:
    """Link slide visual requirements to project assets."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)
        self._presentations = PresentationRepository(session)

    def match_presentation_slides(
        self,
        project_id: UUID,
        presentation_id: UUID,
        *,
        min_score: float = 0.35,
        rematch: bool = False,
    ) -> tuple[list[SlideSpec], int]:
        """Populate preferred_asset_ids and return updated slides plus match count."""
        assets = self._assets.list_by_project(project_id)
        slides = self._presentations.list_slides(presentation_id)
        if not slides:
            return [], 0

        match_count = 0
        updated: list[SlideSpec] = []
        for slide in slides:
            if not slide.visual_requirements:
                updated.append(slide)
                continue

            changed = False
            for requirement in slide.visual_requirements:
                if requirement.preferred_asset_ids and not rematch:
                    match_count += len(requirement.preferred_asset_ids)
                    infer_visual_processing_flags(requirement)
                    continue
                if requirement.confirmed and not rematch:
                    if requirement.preferred_asset_ids:
                        match_count += 1
                    continue
                if requirement.type == VisualType.TEXT_ONLY:
                    continue

                ranked = rank_assets_for_requirement(
                    requirement,
                    assets,
                    min_score=min_score,
                )
                if apply_asset_match(requirement, ranked, overwrite=rematch):
                    changed = True
                if requirement.preferred_asset_ids:
                    match_count += 1

            updated.append(self._presentations.save_slide(slide) if changed else slide)

        return updated, match_count
