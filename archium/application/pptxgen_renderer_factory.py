"""Wire PptxGenPresentationRenderer with application ports (layering phase-2)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.image_search_settings_service import ImageSearchSettingsService
from archium.application.visual.asset_reference import build_asset_reference_context
from archium.application.visual_fallback_service import VisualFallbackService
from archium.config.settings import Settings, get_settings
from archium.domain.fact import ProjectFact
from archium.domain.fallback_image import FallbackImage
from archium.domain.slide import SlideSpec
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer


def _session_api_key(name: str) -> str | None:
    try:
        import streamlit as st
    except ImportError:
        return None
    value = st.session_state.get(name)
    return value if isinstance(value, str) and value else None


def create_pptxgen_renderer(
    settings: Settings | None = None,
    *,
    session: Session | None = None,
    theme: str = "architecture-board",
    pexels_session_api_key: str | None = None,
    unsplash_session_api_key: str | None = None,
) -> PptxGenPresentationRenderer:
    """Construct a PptxGen renderer with fallback / asset-ref ports when session is set."""
    resolved = settings or get_settings()
    fallback_resolver = None
    content_ref_resolver = None

    if session is not None:

        def fallback_resolver(
            project_id: UUID,
            slides: list[SlideSpec],
            *,
            output_dir: Path,
            base_paths: dict[UUID, Path],
            facts: list[ProjectFact],
        ) -> dict[tuple[UUID, int], FallbackImage]:
            preferences = ImageSearchSettingsService(session).get_preferences(
                base_settings=resolved,
            )
            return VisualFallbackService(
                session,
                settings=resolved,
                pexels_session_api_key=(
                    pexels_session_api_key
                    if pexels_session_api_key is not None
                    else _session_api_key("pexels_session_api_key")
                ),
                unsplash_session_api_key=(
                    unsplash_session_api_key
                    if unsplash_session_api_key is not None
                    else _session_api_key("unsplash_session_api_key")
                ),
                image_search_preferences=preferences,
            ).resolve_export_images(
                project_id,
                slides,
                output_dir=output_dir,
                base_paths=base_paths,
                facts=facts,
            )

        def content_ref_resolver(project_id: UUID, content_refs: list[str]) -> dict[str, str]:
            context = build_asset_reference_context(
                session,
                project_id=project_id,
                content_refs=content_refs,
                settings=resolved,
            )
            return dict(context.resolved_paths)

    return PptxGenPresentationRenderer(
        resolved,
        session=session,
        theme=theme,
        fallback_image_resolver=fallback_resolver,
        content_ref_path_resolver=content_ref_resolver,
    )
