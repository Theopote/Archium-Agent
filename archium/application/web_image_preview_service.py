"""Preview and adopt licensed web images from the Asset Board."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_board_service import AssetBoardService
from archium.application.image_search_settings_service import ImageSearchPreferences
from archium.application.web_image_asset_service import WebImageAssetService
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import VisualType
from archium.domain.fact import ProjectFact
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.images.web_search import WebImageSearchService
from archium.infrastructure.images.web_search.models import WebImageCandidate

_PREVIEW_LIMIT = 6


@dataclass(frozen=True)
class WebImagePreviewItem:
    provider: str
    candidate: WebImageCandidate


@dataclass(frozen=True)
class WebImagePreviewResult:
    query: str
    items: list[WebImagePreviewItem]


class WebImagePreviewService:
    """Search stock providers for preview, then adopt a chosen candidate into the project."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        pexels_session_api_key: str | None = None,
        unsplash_session_api_key: str | None = None,
        image_search_preferences: ImageSearchPreferences | None = None,
        web_search: WebImageSearchService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._preferences = image_search_preferences
        effective = self._effective_settings
        self._web_search = web_search or WebImageSearchService(
            effective,
            session_pexels_api_key=pexels_session_api_key,
            session_unsplash_api_key=unsplash_session_api_key,
        )
        self._web_assets = WebImageAssetService(session, settings=effective)
        self._board = AssetBoardService(session)
        self._presentations = PresentationRepository(session)

    @property
    def configured(self) -> bool:
        return self._web_search.configured and self._effective_settings.web_image_search_enabled

    def can_preview(self, visual_type: VisualType) -> bool:
        return self._web_search.can_search(visual_type)

    def preview_requirement(
        self,
        slide: SlideSpec,
        requirement: VisualRequirement,
        *,
        facts: list[ProjectFact] | None = None,
        limit: int = _PREVIEW_LIMIT,
    ) -> WebImagePreviewResult | None:
        if not self.can_preview(requirement.type):
            return None
        query, items = self._web_search.search_candidates(
            slide,
            requirement,
            facts=facts,
            limit=limit,
        )
        if not items:
            return None
        return WebImagePreviewResult(
            query=query,
            items=[
                WebImagePreviewItem(provider=provider, candidate=candidate)
                for provider, candidate in items
            ],
        )

    def adopt_candidate(
        self,
        project_id: UUID,
        slide_id: UUID,
        requirement_index: int,
        *,
        item: WebImagePreviewItem,
        search_query: str,
        confirm: bool = True,
    ) -> Asset:
        slide = self._require_slide(slide_id)
        requirement = self._require_requirement(slide, requirement_index)
        asset = self._web_assets.import_candidate(
            project_id,
            item.candidate,
            slide=slide,
            requirement=requirement,
            search_query=search_query,
            provider=item.provider,
        )
        self._board.assign_asset(slide_id, requirement_index, asset.id)
        if confirm:
            self._board.confirm_assignment(slide_id, requirement_index)
        return asset

    def _require_slide(self, slide_id: UUID) -> SlideSpec:
        slide = self._presentations.get_slide(slide_id)
        if slide is None:
            raise WorkflowError(f"Slide {slide_id} not found")
        return slide

    def _require_requirement(self, slide: SlideSpec, requirement_index: int) -> VisualRequirement:
        if requirement_index < 0 or requirement_index >= len(slide.visual_requirements):
            raise WorkflowError(f"Visual requirement index {requirement_index} out of range")
        return slide.visual_requirements[requirement_index]

    @property
    def _effective_settings(self) -> Settings:
        if self._preferences is None:
            return self._settings
        return self._settings.model_copy(
            update={
                "web_image_search_enabled": self._preferences.enabled,
                "web_image_search_persist_to_library": self._preferences.persist_to_library,
            }
        )
