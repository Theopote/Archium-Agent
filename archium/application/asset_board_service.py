"""Asset Board — flattened view of slide visual requirements and asset assignments."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_matching_service import (
    AssetMatchingService,
    score_asset_for_requirement,
)
from archium.application.asset_provenance import format_asset_provenance
from archium.domain.asset import Asset
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    AssetRepository,
    DocumentRepository,
    PresentationRepository,
)


@dataclass
class AssetBoardRow:
    slide_id: UUID
    slide_order: int
    slide_title: str
    requirement_index: int
    visual_type: str
    description: str
    required: bool
    candidate_asset_id: UUID | None
    candidate_asset_ids: list[UUID]
    match_score: float | None
    asset_filename: str | None
    asset_source: str | None
    asset_page: int | None
    resolution: str | None
    aspect_ratio: float | None
    confirmed: bool
    needs_crop: bool
    needs_highlight: bool
    low_resolution: bool
    web_search_eligible: bool = False


@dataclass
class AssetBoardView:
    project_id: UUID
    presentation_id: UUID
    rows: list[AssetBoardRow]
    asset_count: int
    matched_count: int
    confirmed_count: int
    pending_count: int


class AssetBoardService:
    """Build and update the presentation asset board."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)
        self._documents = DocumentRepository(session)
        self._presentations = PresentationRepository(session)
        self._matcher = AssetMatchingService(session)

    def build_board(self, project_id: UUID, presentation_id: UUID) -> AssetBoardView:
        slides = self._presentations.list_slides(presentation_id)
        assets = self._assets.list_by_project(project_id)
        assets_by_id = {asset.id: asset for asset in assets}
        document_names = self._document_name_map(assets)

        rows: list[AssetBoardRow] = []
        matched_count = 0
        confirmed_count = 0
        pending_count = 0

        for slide in sorted(slides, key=lambda item: item.order):
            for index, requirement in enumerate(slide.visual_requirements):
                if requirement.type == VisualType.TEXT_ONLY:
                    continue
                row = self._build_row(
                    slide=slide,
                    requirement_index=index,
                    requirement=requirement,
                    assets_by_id=assets_by_id,
                    document_names=document_names,
                )
                rows.append(row)
                if row.candidate_asset_id is not None:
                    matched_count += 1
                if row.confirmed:
                    confirmed_count += 1
                elif row.required:
                    pending_count += 1

        return AssetBoardView(
            project_id=project_id,
            presentation_id=presentation_id,
            rows=rows,
            asset_count=len(assets),
            matched_count=matched_count,
            confirmed_count=confirmed_count,
            pending_count=pending_count,
        )

    def rematch(self, project_id: UUID, presentation_id: UUID) -> AssetBoardView:
        self._matcher.match_presentation_slides(
            project_id,
            presentation_id,
            rematch=True,
        )
        return self.build_board(project_id, presentation_id)

    def assign_asset(
        self,
        slide_id: UUID,
        requirement_index: int,
        asset_id: UUID,
    ) -> SlideSpec:
        slide = self._require_slide(slide_id)
        requirement = self._require_requirement(slide, requirement_index)
        asset = self._require_asset(asset_id)
        requirement.preferred_asset_ids = [asset.id]
        requirement.match_score = score_asset_for_requirement(requirement, asset)
        requirement.confirmed = False
        if asset.id not in requirement.candidate_asset_ids:
            requirement.candidate_asset_ids = [asset.id, *requirement.candidate_asset_ids][:3]
        slide.version += 1
        return self._presentations.save_slide(slide)

    def confirm_assignment(self, slide_id: UUID, requirement_index: int) -> SlideSpec:
        slide = self._require_slide(slide_id)
        requirement = self._require_requirement(slide, requirement_index)
        if not requirement.preferred_asset_ids:
            raise WorkflowError("Cannot confirm visual assignment without a selected asset")
        requirement.confirmed = True
        slide.version += 1
        return self._presentations.save_slide(slide)

    def update_assignment_flags(
        self,
        slide_id: UUID,
        requirement_index: int,
        *,
        needs_crop: bool,
        needs_highlight: bool,
    ) -> SlideSpec:
        slide = self._require_slide(slide_id)
        requirement = self._require_requirement(slide, requirement_index)
        requirement.needs_crop = needs_crop
        requirement.needs_highlight = needs_highlight
        slide.version += 1
        return self._presentations.save_slide(slide)

    def list_project_assets(self, project_id: UUID) -> list[Asset]:
        return self._assets.list_by_project(project_id)

    def _build_row(
        self,
        *,
        slide: SlideSpec,
        requirement_index: int,
        requirement: VisualRequirement,
        assets_by_id: dict[UUID, Asset],
        document_names: dict[UUID, str],
    ) -> AssetBoardRow:
        asset_id = requirement.primary_asset_id
        asset = assets_by_id.get(asset_id) if asset_id is not None else None
        resolution = None
        aspect_ratio = None
        asset_source = None
        asset_page = None
        asset_filename = None
        low_resolution = False

        if asset is not None:
            asset_filename = asset.filename
            asset_page = asset.page_number
            low_resolution = asset.is_low_resolution
            if asset.width and asset.height:
                resolution = f"{asset.width}×{asset.height}"
            aspect_ratio = asset.aspect_ratio
            asset_source = format_asset_provenance(asset, document_names=document_names)

        web_search_eligible = (
            asset_id is None
            and requirement.type
            in {VisualType.RENDERING, VisualType.SITE_PHOTO, VisualType.REFERENCE_CASE}
        )

        return AssetBoardRow(
            slide_id=slide.id,
            slide_order=slide.order,
            slide_title=slide.title,
            requirement_index=requirement_index,
            visual_type=requirement.type.value,
            description=requirement.description,
            required=requirement.required,
            candidate_asset_id=asset_id,
            candidate_asset_ids=list(requirement.candidate_asset_ids),
            match_score=requirement.match_score,
            asset_filename=asset_filename,
            asset_source=asset_source,
            asset_page=asset_page,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            confirmed=requirement.confirmed,
            needs_crop=requirement.needs_crop,
            needs_highlight=requirement.needs_highlight,
            low_resolution=low_resolution,
            web_search_eligible=web_search_eligible,
        )

    def _document_name_map(self, assets: list[Asset]) -> dict[UUID, str]:
        names: dict[UUID, str] = {}
        for asset in assets:
            if asset.document_id is None or asset.document_id in names:
                continue
            document = self._documents.get_document(asset.document_id)
            if document is not None:
                names[asset.document_id] = document.filename
        return names

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"Slide {slide_id} not found")
        return slide

    def _require_requirement(self, slide: SlideSpec, requirement_index: int) -> VisualRequirement:
        if requirement_index < 0 or requirement_index >= len(slide.visual_requirements):
            raise WorkflowError(f"Visual requirement index {requirement_index} out of range")
        return slide.visual_requirements[requirement_index]

    def _require_asset(self, asset_id: UUID) -> Asset:
        asset = self._assets.get_by_id(asset_id)
        if asset is None:
            raise WorkflowError(f"Asset {asset_id} not found")
        return asset
