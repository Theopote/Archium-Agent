"""Application service — route slide recovery region analysis (structural vs perceptual)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from archium.application.model_role_router import ModelRoleRouter, audit_model_call
from archium.application.model_role_router import ModelRoleRegistryService
from archium.config.settings import Settings, get_settings
from archium.domain.model_roles import ModelRole
from archium.domain.slide_recovery import RecoveredPageRegion, SlideRecoveryPageKind
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.slide_recovery.perceptual_region_adapter import (
    PerceptualAnalysisResult,
    is_raster_proxy_scene,
    regions_from_page_image,
    resolve_page_image_path,
)
from archium.infrastructure.slide_recovery.scene_region_adapter import (
    classify_page_kind,
    regions_from_render_scene,
)
from archium.infrastructure.slide_recovery.structural_perceptual_merge import (
    merge_structural_and_perceptual,
)
from archium.infrastructure.slide_recovery.vlm_region_analyzer import VlmRegionAnalyzer


@dataclass(frozen=True)
class RegionAnalysisResult:
    regions: list[RecoveredPageRegion]
    page_kind: SlideRecoveryPageKind
    mode: str
    ocr_engine: str | None = None
    vlm_source: str | None = None
    ocr_char_count: int = 0


class SlideRecoveryRegionAnalyzer:
    """Choose structural, perceptual, or hybrid region analysis for a page."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        settings: Settings | None = None,
        vlm_analyzer: VlmRegionAnalyzer | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._router: ModelRoleRouter | None = None
        if session is not None:
            self._router = ModelRoleRouter(ModelRoleRegistryService(session))
        self._vlm = vlm_analyzer or VlmRegionAnalyzer(settings=self._settings)

    def analyze(
        self,
        scene: RenderScene,
        *,
        source_page_id: str,
        source_image_path: Path | str | None = None,
        page_kind: SlideRecoveryPageKind | None = None,
        force_perceptual: bool = False,
        source_kind: str | None = None,
    ) -> RegionAnalysisResult:
        image_path = resolve_page_image_path(scene, source_image_path)
        raster_scene = is_raster_proxy_scene(scene)
        use_perceptual = force_perceptual or (image_path is not None and raster_scene)
        use_hybrid = (
            not use_perceptual
            and image_path is not None
            and not raster_scene
            and self._settings.slide_recovery_pptx_perceptual_enabled
            and source_kind in {None, "pptx"}
        )

        if use_perceptual and image_path is not None:
            started = time.perf_counter()
            perceptual = regions_from_page_image(
                scene,
                image_path,
                page_kind=page_kind,
                vlm_analyzer=self._vlm,
                ocr_enabled=self._settings.slide_recovery_ocr_enabled,
            )
            self._audit_roles(
                source_page_id=source_page_id,
                mode="perceptual",
                perceptual=perceptual,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return RegionAnalysisResult(
                regions=perceptual.regions,
                page_kind=perceptual.page_kind,
                mode="perceptual",
                ocr_engine=perceptual.ocr_engine,
                vlm_source=perceptual.vlm_source,
                ocr_char_count=perceptual.ocr_char_count,
            )

        resolved_kind = page_kind or classify_page_kind(scene)
        structural_regions = regions_from_render_scene(scene, page_kind=resolved_kind)

        if use_hybrid and image_path is not None:
            started = time.perf_counter()
            perceptual = regions_from_page_image(
                scene,
                image_path,
                page_kind=resolved_kind,
                vlm_analyzer=self._vlm,
                ocr_enabled=self._settings.slide_recovery_ocr_enabled,
            )
            merged = merge_structural_and_perceptual(structural_regions, perceptual.regions)
            self._audit_roles(
                source_page_id=source_page_id,
                mode="hybrid",
                perceptual=perceptual,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return RegionAnalysisResult(
                regions=merged,
                page_kind=resolved_kind,
                mode="hybrid",
                ocr_engine=perceptual.ocr_engine,
                vlm_source=perceptual.vlm_source,
                ocr_char_count=perceptual.ocr_char_count,
            )

        return RegionAnalysisResult(
            regions=structural_regions,
            page_kind=resolved_kind,
            mode="structural",
        )

    def _audit_roles(
        self,
        *,
        source_page_id: str,
        mode: str,
        perceptual: PerceptualAnalysisResult,
        duration_ms: float,
    ) -> None:
        if self._router is None:
            return
        ocr_success = perceptual.ocr_engine is not None or perceptual.ocr_char_count == 0
        vlm_success = perceptual.vlm_source in {"llm_vision", "heuristic"}
        role_outcomes = (
            (ModelRole.OCR, ocr_success, perceptual.ocr_engine or "unavailable"),
            (ModelRole.VISION, vlm_success, perceptual.vlm_source or "unavailable"),
        )
        for role, success, detail in role_outcomes:
            profile = self._router.resolve_optional(role)
            if profile is None:
                continue
            audit_model_call(
                profile,
                role,
                request_id=f"slide_recovery:{source_page_id}:{mode}:{detail}",
                slide_id=None,
                duration_ms=duration_ms,
                success=success,
                failure_type=None if success else detail,
            )
