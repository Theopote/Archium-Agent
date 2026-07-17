"""Match project assets to slide visual requirements."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

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


def _score_asset(requirement: VisualRequirement, asset: Asset) -> float:
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
                if requirement.preferred_asset_ids:
                    match_count += len(requirement.preferred_asset_ids)
                    continue
                if requirement.type == VisualType.TEXT_ONLY:
                    continue

                ranked = sorted(
                    ((asset, _score_asset(requirement, asset)) for asset in assets),
                    key=lambda item: item[1],
                    reverse=True,
                )
                best = next(((asset, score) for asset, score in ranked if score >= min_score), None)
                if best is None:
                    continue
                asset, _score = best
                requirement.preferred_asset_ids = [asset.id]
                match_count += 1
                changed = True

            updated.append(self._presentations.save_slide(slide) if changed else slide)

        return updated, match_count
