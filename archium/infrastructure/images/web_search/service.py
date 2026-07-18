"""Orchestrate licensed web image search for export fallbacks."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.enums import VisualType
from archium.domain.fact import ProjectFact
from archium.domain.fallback_image import FallbackImage
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.credentials.resolver import resolve_pexels_api_key, resolve_unsplash_access_key
from archium.infrastructure.images.web_search.downloader import download_image, is_safe_https_url
from archium.infrastructure.images.web_search.models import WebImageCandidate
from archium.infrastructure.images.web_search.pexels import PexelsClient
from archium.infrastructure.images.web_search.query_builder import build_search_query
from archium.infrastructure.images.web_search.unsplash import UnsplashClient

_WEB_SEARCH_TYPES = {
    VisualType.RENDERING,
    VisualType.SITE_PHOTO,
    VisualType.REFERENCE_CASE,
}


class WebSearchProvider(Protocol):
    provider_name: str

    def search(self, query: str, *, per_page: int = 5) -> list[WebImageCandidate]: ...


class WebImageSearchService:
    """Search stock photo providers and download the first suitable image."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session_pexels_api_key: str | None = None,
        session_unsplash_api_key: str | None = None,
        providers: list[WebSearchProvider] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session_pexels_api_key = session_pexels_api_key
        self._session_unsplash_api_key = session_unsplash_api_key
        self._providers = providers

    @property
    def configured(self) -> bool:
        return bool(self._build_providers())

    def can_search(self, visual_type: VisualType) -> bool:
        return (
            self._settings.web_image_search_enabled
            and visual_type in _WEB_SEARCH_TYPES
            and self.configured
        )

    def resolve_requirement(
        self,
        slide: SlideSpec,
        requirement: VisualRequirement,
        requirement_index: int,
        *,
        output_dir: Path,
        facts: list[ProjectFact] | None = None,
    ) -> FallbackImage | None:
        if not self.can_search(requirement.type):
            return None

        query = build_search_query(slide, requirement, facts=facts)
        dest = output_dir / "generated" / self._output_name(slide.id, requirement_index)
        for provider in self._build_providers():
            candidates = provider.search(
                query,
                per_page=self._settings.web_image_search_per_page,
            )
            for candidate in candidates:
                downloaded = self._try_download_candidate(candidate, dest)
                if downloaded is not None:
                    return FallbackImage(
                        path=downloaded,
                        generated=True,
                        web_sourced=True,
                        attribution=candidate.attribution,
                        source_url=candidate.page_url,
                        search_query=query,
                        provider=provider.provider_name,
                    )
        return None

    def search_candidates(
        self,
        slide: SlideSpec,
        requirement: VisualRequirement,
        *,
        facts: list[ProjectFact] | None = None,
        limit: int = 6,
    ) -> tuple[str, list[tuple[str, WebImageCandidate]]]:
        """Return query text and provider/candidate pairs without downloading."""
        query = build_search_query(slide, requirement, facts=facts)
        results: list[tuple[str, WebImageCandidate]] = []
        for provider in self._build_providers():
            candidates = provider.search(
                query,
                per_page=self._settings.web_image_search_per_page,
            )
            for candidate in candidates:
                results.append((provider.provider_name, candidate))
                if len(results) >= limit:
                    return query, results
        return query, results

    def _build_providers(self) -> list[WebSearchProvider]:
        if self._providers is not None:
            return self._providers

        providers: list[WebSearchProvider] = []
        pexels_key, _ = resolve_pexels_api_key(
            session_api_key=self._session_pexels_api_key,
            env_api_key=self._settings.pexels_api_key,
        )
        if pexels_key:
            providers.append(
                _NamedProvider(
                    "pexels",
                    PexelsClient(
                        pexels_key,
                        timeout=self._settings.web_image_search_timeout_seconds,
                    ),
                )
            )

        unsplash_key, _ = resolve_unsplash_access_key(
            session_api_key=self._session_unsplash_api_key,
            env_api_key=self._settings.unsplash_access_key,
        )
        if unsplash_key:
            providers.append(
                _NamedProvider(
                    "unsplash",
                    UnsplashClient(
                        unsplash_key,
                        timeout=self._settings.web_image_search_timeout_seconds,
                    ),
                )
            )
        return providers

    @staticmethod
    def _output_name(slide_id: UUID, requirement_index: int) -> Path:
        return Path(f"web_{slide_id}_{requirement_index}.jpg")

    def _try_download_candidate(self, candidate: WebImageCandidate, dest: Path) -> Path | None:
        if not is_safe_https_url(candidate.download_url):
            return None
        try:
            return download_image(
                candidate.download_url,
                dest,
                timeout=self._settings.web_image_search_timeout_seconds,
            )
        except (OSError, ValueError):
            return None


class _NamedProvider:
    def __init__(self, name: str, client: WebSearchProvider) -> None:
        self.provider_name = name
        self._client = client

    def search(self, query: str, *, per_page: int = 5) -> list[WebImageCandidate]:
        return self._client.search(query, per_page=per_page)
