"""Export policy enforcement and deck fidelity manifest assembly."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings, get_settings
from archium.domain.export_fidelity import (
    DeckExportManifest,
    ExportFidelityLevel,
    ExportPolicy,
    SlideExportResult,
    fidelity_rank,
    policy_allows_fidelity,
    worst_fidelity,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.exceptions import WorkflowError

_FULL_PAGE_AREA_RATIO = 0.85


class ExportPolicyService:
    """Assess slide fidelity, build manifests, and enforce export policy."""

    def assess_scene_fidelity(self, scene: RenderScene) -> SlideExportResult:
        """Derive per-slide fidelity from a RenderScene (pre/post export)."""
        text_nodes = [n for n in scene.nodes if isinstance(n, TextNode)]
        shape_nodes = [n for n in scene.nodes if isinstance(n, ShapeNode)]
        drawing_nodes = [n for n in scene.nodes if isinstance(n, DrawingNode)]
        image_nodes = [n for n in scene.nodes if isinstance(n, ImageNode)]

        native_text = sum(1 for n in text_nodes if n.text.strip())
        native_shapes = len(shape_nodes)
        bitmap_count = len(drawing_nodes) + len(image_nodes)

        blockers: list[str] = []
        warnings: list[str] = []
        unresolved: list[str] = []
        font_subs: list[str] = []

        page_area = scene.page_width * scene.page_height
        for node in drawing_nodes:
            if node.fit_mode not in {"contain", "safe_crop"}:
                blockers.append(f"drawing:{node.id}:fit_mode={node.fit_mode}")
            if node.asset_unresolved:
                unresolved.append(node.id)

        for node in image_nodes:
            if node.asset_unresolved:
                unresolved.append(node.id)
            if (
                _node_area(node, page_area) >= page_area * _FULL_PAGE_AREA_RATIO
                and native_text == 0
            ):
                warnings.append(f"full_page_image:{node.id}")

        for font in scene.font_assets:
            if font.resolved_family and font.resolved_family != font.family:
                font_subs.append(f"{font.family}→{font.resolved_family}")

        fidelity = self._classify_fidelity(
            native_text=native_text,
            native_shapes=native_shapes,
            bitmap_count=bitmap_count,
            scene=scene,
            page_area=page_area,
            warnings=warnings,
        )

        return SlideExportResult(
            slide_id=scene.slide_id,
            fidelity_level=fidelity,
            native_text_count=native_text,
            native_shape_count=native_shapes,
            bitmap_asset_count=bitmap_count,
            font_substitutions=font_subs,
            unresolved_assets=unresolved,
            warnings=warnings,
            blockers=blockers,
        )

    def build_deck_manifest(
        self,
        *,
        presentation_id: UUID,
        export_format: str,
        policy: ExportPolicy,
        slide_results: list[SlideExportResult],
        revision_id: UUID | None = None,
        file_uri: str | None = None,
        file_hash: str | None = None,
        qa_status: str = "unknown",
    ) -> DeckExportManifest:
        final = worst_fidelity([slide.fidelity_level for slide in slide_results])
        fallback_used = any(
            slide.fidelity_level != ExportFidelityLevel.FULLY_EDITABLE
            for slide in slide_results
        )
        fallback_reason: str | None = None
        if fallback_used:
            degraded = [
                slide
                for slide in slide_results
                if slide.fidelity_level != ExportFidelityLevel.FULLY_EDITABLE
            ]
            levels = sorted(
                {slide.fidelity_level for slide in degraded},
                key=fidelity_rank,
                reverse=True,
            )
            fallback_reason = "；".join(
                f"{level.value}×{sum(1 for s in degraded if s.fidelity_level == level)}"
                for level in levels
            )

        return DeckExportManifest(
            presentation_id=presentation_id,
            revision_id=revision_id,
            export_format=export_format,
            requested_policy=policy,
            final_fidelity=final,
            slides=slide_results,
            file_uri=file_uri,
            file_hash=file_hash,
            qa_status=qa_status,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )

    def enforce_export_policy(
        self,
        manifest: DeckExportManifest,
        *,
        policy: ExportPolicy | None = None,
    ) -> None:
        """Raise WorkflowError when export would silently degrade below policy."""
        active = policy or manifest.requested_policy

        for slide in manifest.slides:
            if slide.blockers and active.fail_on_drawing_crop:
                crop_blockers = [b for b in slide.blockers if b.startswith("drawing:")]
                if crop_blockers:
                    raise WorkflowError(
                        f"页面 {slide.slide_id} 存在图纸保护阻塞项，禁止导出："
                        + "；".join(crop_blockers)
                    )

            if slide.unresolved_assets and active.fail_on_unresolved_assets:
                raise WorkflowError(
                    f"页面 {slide.slide_id} 存在未解析素材，禁止导出："
                    + "；".join(slide.unresolved_assets)
                )

            if slide.font_substitutions and active.fail_on_missing_fonts:
                raise WorkflowError(
                    f"页面 {slide.slide_id} 存在字体替代："
                    + "；".join(slide.font_substitutions)
                )

            if not policy_allows_fidelity(active, slide.fidelity_level):
                label = slide.fidelity_level.value
                raise WorkflowError(
                    f"页面忠实度为 {label}，超出当前导出策略允许范围。"
                    "请调整「导出策略」或修复页面后再导出。"
                )

        required_rank = fidelity_rank(active.required_fidelity)
        for slide in manifest.slides:
            if (
                fidelity_rank(slide.fidelity_level) > required_rank
                and not active.allow_slide_level_fallback
            ):
                raise WorkflowError(
                    f"存在 {slide.fidelity_level.value} 页面，"
                    f"不满足要求的 {active.required_fidelity.value}。"
                    "系统不会静默降级为图片式 PPTX。"
                )

        if (
            manifest.final_fidelity == ExportFidelityLevel.RASTER_FALLBACK
            and not active.allow_raster_fallback
        ):
            raise WorkflowError(
                "导出结果将为整页图片式 PPTX，但当前策略禁止图片降级。"
                "请修复页面或显式启用「允许图片式降级」。"
            )

    def _classify_fidelity(
        self,
        *,
        native_text: int,
        native_shapes: int,
        bitmap_count: int,
        scene: RenderScene,
        page_area: float,
        warnings: list[str],
    ) -> ExportFidelityLevel:
        if not scene.nodes and not scene.background.image_asset_path:
            return ExportFidelityLevel.FAILED

        has_bg_image = bool(scene.background.image_asset_path)
        editable_nodes = native_text + native_shapes

        full_page_images = [
            n
            for n in scene.nodes
            if isinstance(n, ImageNode) and _node_area(n, page_area) >= page_area * _FULL_PAGE_AREA_RATIO
        ]
        if len(full_page_images) == 1 and editable_nodes == 0 and bitmap_count <= 1:
            return ExportFidelityLevel.RASTER_FALLBACK

        if has_bg_image and editable_nodes > 0 and bitmap_count == 0:
            return ExportFidelityLevel.TEXT_EDITABLE

        if native_text > 0 and bitmap_count > 0:
            return ExportFidelityLevel.HYBRID_EDITABLE

        if editable_nodes > 0:
            return ExportFidelityLevel.FULLY_EDITABLE

        if bitmap_count > 0:
            return ExportFidelityLevel.HYBRID_EDITABLE

        return ExportFidelityLevel.FAILED


def _node_area(node: object, page_area: float) -> float:
    width = getattr(node, "width", 0.0) or 0.0
    height = getattr(node, "height", 0.0) or 0.0
    return width * height if page_area > 0 else 0.0


def build_pre_export_manifest(
    session: Session,
    *,
    presentation_id: UUID,
    policy: ExportPolicy,
    export_format: str = "PPTX",
    revision_id: UUID | None = None,
    settings: Settings | None = None,
) -> DeckExportManifest:
    """Compile RenderScenes and assess fidelity before writing export files."""
    scene_service = StudioSceneService(session, settings=settings or get_settings())
    scene_results = scene_service.ensure_scenes_for_presentation(
        presentation_id,
        force_recompile=False,
    )
    service = ExportPolicyService()
    slide_results = [service.assess_scene_fidelity(result.scene) for result in scene_results]
    return service.build_deck_manifest(
        presentation_id=presentation_id,
        export_format=export_format,
        policy=policy,
        slide_results=slide_results,
        revision_id=revision_id,
    )


def export_policy_from_preset(preset: str) -> ExportPolicy:
    """Map UI preset keys to ExportPolicy."""
    presets: dict[str, ExportPolicy] = {
        "strict_native": ExportPolicy(
            required_fidelity=ExportFidelityLevel.FULLY_EDITABLE,
            allow_hybrid_editable=False,
            allow_text_editable_background=False,
            allow_raster_fallback=False,
        ),
        "allow_hybrid": ExportPolicy(
            required_fidelity=ExportFidelityLevel.FULLY_EDITABLE,
            allow_slide_level_fallback=True,
            allow_hybrid_editable=True,
            allow_text_editable_background=False,
            allow_raster_fallback=False,
        ),
        "allow_text_bg": ExportPolicy(
            required_fidelity=ExportFidelityLevel.HYBRID_EDITABLE,
            allow_slide_level_fallback=True,
            allow_hybrid_editable=True,
            allow_text_editable_background=True,
            allow_raster_fallback=False,
        ),
        "allow_raster": ExportPolicy(
            required_fidelity=ExportFidelityLevel.TEXT_EDITABLE,
            allow_slide_level_fallback=True,
            allow_hybrid_editable=True,
            allow_text_editable_background=True,
            allow_raster_fallback=True,
        ),
    }
    return presets.get(preset, presets["strict_native"])
