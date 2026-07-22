"""Slide Recovery spike service — OCR + VLM region analysis → HybridRenderScene.

Technical validation only; does not enter the main materials → deliver pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.model_role_router import ModelRoleRouter, audit_model_call
from archium.application.model_role_router import ModelRoleRegistryService
from archium.domain.export_fidelity import ExportFidelityLevel
from archium.domain.model_roles import ModelRole
from archium.domain.slide_recovery import (
    HybridRenderScene,
    NormalizedBox,
    RecoveredPageRegion,
    SlideRecoveryMetrics,
    SlideRecoveryPageKind,
    SlideRecoveryResult,
    infer_reconstruction_fidelity,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.infrastructure.slide_recovery.scene_region_adapter import (
    build_render_scene_from_regions,
    classify_page_kind,
    partition_regions,
    regions_from_render_scene,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlideRecoveryRequest:
    """Input for a single-page recovery spike run."""

    source_page_id: str
    source_scene: RenderScene
    page_kind: SlideRecoveryPageKind | None = None
    # Optional controlled degradation for spike experiments.
    position_noise: float = 0.0
    drop_text_ratio: float = 0.0
    force_table_bitmap: bool = False


class SlideRecoveryService:
    """Recover a hybrid RenderScene from a source page (spike)."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session
        self._router: ModelRoleRouter | None = None
        if session is not None:
            self._router = ModelRoleRouter(ModelRoleRegistryService(session))

    def recover_page(self, request: SlideRecoveryRequest) -> SlideRecoveryResult:
        page_kind = request.page_kind or classify_page_kind(request.source_scene)
        self._audit_spike_roles(request.source_page_id)

        regions = regions_from_render_scene(request.source_scene, page_kind=page_kind)
        regions = self._apply_spike_transforms(regions, request)
        regions = self._apply_table_bitmap_policy(regions, request, page_kind)

        text_regions, visual_regions, native_shapes = partition_regions(regions)
        recovered_scene, bitmap_ids = build_render_scene_from_regions(
            request.source_scene,
            regions,
            source_page_id=request.source_page_id,
            page_kind=page_kind,
        )

        metrics = evaluate_recovery_metrics(
            request.source_scene,
            recovered_scene,
            regions,
            exclude_text_roles={"table_cell"} if request.force_table_bitmap else None,
        )
        fidelity = infer_reconstruction_fidelity(metrics)
        warnings, blockers = self._collect_issues(metrics, fidelity, page_kind)

        hybrid = HybridRenderScene(
            scene=recovered_scene,
            recovery_source_id=request.source_page_id,
            page_kind=page_kind,
            regions=regions,
            reconstruction_fidelity=fidelity,
            hybrid_bitmap_region_ids=bitmap_ids,
            metrics=metrics,
        )

        return SlideRecoveryResult(
            source_page_id=request.source_page_id,
            recovered_scene_id=recovered_scene.id,
            text_regions=text_regions,
            visual_regions=visual_regions,
            native_shape_regions=native_shapes,
            reconstruction_fidelity=fidelity,
            metrics=metrics,
            hybrid_scene=hybrid,
            warnings=warnings,
            blockers=blockers,
        )

    def _audit_spike_roles(self, source_page_id: str) -> None:
        if self._router is None:
            return
        for role in (ModelRole.OCR, ModelRole.VISION):
            profile = self._router.resolve_optional(role)
            if profile is None:
                logger.debug(
                    "slide_recovery spike: role %s not configured for %s",
                    role.value,
                    source_page_id,
                )
                continue
            audit_model_call(
                profile,
                role,
                request_id=f"slide_recovery:{source_page_id}",
                slide_id=None,
                success=True,
            )

    def _apply_spike_transforms(
        self,
        regions: list[RecoveredPageRegion],
        request: SlideRecoveryRequest,
    ) -> list[RecoveredPageRegion]:
        if request.position_noise <= 0 and request.drop_text_ratio <= 0:
            return regions

        updated: list[RecoveredPageRegion] = []
        text_indices = [index for index, region in enumerate(regions) if region.region_type == "text"]
        drop_count = int(len(text_indices) * request.drop_text_ratio)
        drop_set = set(text_indices[:drop_count])

        for index, region in enumerate(regions):
            if index in drop_set:
                continue
            if request.position_noise > 0:
                bbox = region.bbox
                dx = request.position_noise if index % 2 == 0 else -request.position_noise
                dy = request.position_noise / 2
                new_x = min(max(bbox.x + dx, 0.0), 1.0 - bbox.width)
                new_y = min(max(bbox.y + dy, 0.0), 1.0 - bbox.height)
                region = region.model_copy(
                    update={"bbox": bbox.model_copy(update={"x": new_x, "y": new_y})}
                )
            updated.append(region)
        return updated

    def _apply_table_bitmap_policy(
        self,
        regions: list[RecoveredPageRegion],
        request: SlideRecoveryRequest,
        page_kind: SlideRecoveryPageKind,
    ) -> list[RecoveredPageRegion]:
        if not request.force_table_bitmap:
            return regions
        del page_kind

        updated: list[RecoveredPageRegion] = []
        table_bbox = _merge_table_bbox(regions)
        table_marked = False
        for region in regions:
            if region.region_type == "text" and region.semantic_role == "table_cell":
                if not table_marked and table_bbox is not None:
                    updated.append(
                        RecoveredPageRegion(
                            id=region.id,
                            bbox=table_bbox,
                            region_type="table",
                            semantic_role="table",
                            confidence=0.88,
                            bitmap_fallback=True,
                            source_asset_uri=region.source_asset_uri,
                            source_node_id=region.source_node_id,
                        )
                    )
                    table_marked = True
                continue
            updated.append(region)
        return updated

    def _collect_issues(
        self,
        metrics: SlideRecoveryMetrics,
        fidelity: ExportFidelityLevel,
        page_kind: SlideRecoveryPageKind,
    ) -> tuple[list[str], list[str]]:
        warnings: list[str] = []
        blockers: list[str] = []

        if fidelity == ExportFidelityLevel.HYBRID_EDITABLE:
            warnings.append(
                f"{page_kind.value}：未达全部指标，已标记为混合可编辑（文字原生 + 复杂区域 Bitmap）。"
            )
        elif fidelity == ExportFidelityLevel.TEXT_EDITABLE:
            warnings.append("仅文字可编辑；复杂视觉与图纸保持 Bitmap / 整体对象。")
        elif fidelity == ExportFidelityLevel.RASTER_FALLBACK:
            blockers.append("恢复质量不足，建议整页 Bitmap 降级。")

        if not metrics.drawing_integrity_ok:
            blockers.append("建筑图纸完整性检查未通过。")
        if not metrics.asset_identity_preserved:
            warnings.append("素材身份可能混淆，需人工复核。")

        return warnings, blockers


def evaluate_recovery_metrics(
    source: RenderScene,
    recovered: RenderScene,
    regions: list[RecoveredPageRegion],
    *,
    exclude_text_roles: set[str] | None = None,
) -> SlideRecoveryMetrics:
    """Compute spike QA metrics between source and recovered scenes."""
    excluded = exclude_text_roles or set()
    source_texts = [
        node
        for node in source.nodes
        if isinstance(node, TextNode) and node.semantic_role not in excluded
    ]
    recovered_texts = [node for node in recovered.nodes if isinstance(node, TextNode)]

    matched = 0
    position_errors: list[float] = []
    recovered_by_role: dict[str, TextNode] = {}
    for node in recovered_texts:
        key = f"{node.semantic_role}:{node.text.strip()}"
        recovered_by_role[key] = node

    region_by_node = {region.source_node_id: region for region in regions if region.source_node_id}

    for node in source_texts:
        key = f"{node.semantic_role}:{node.text.strip()}"
        recovered_node = recovered_by_role.get(key)
        if recovered_node is None:
            continue
        matched += 1
        source_region = region_by_node.get(node.id)
        if source_region is not None:
            source_bbox = NormalizedBox.from_absolute(
                x=node.x,
                y=node.y,
                width=node.width,
                height=node.height,
                page_width=source.page_width,
                page_height=source.page_height,
            )
            recovered_bbox = NormalizedBox.from_absolute(
                x=recovered_node.x,
                y=recovered_node.y,
                width=recovered_node.width,
                height=recovered_node.height,
                page_width=source.page_width,
                page_height=source.page_height,
            )
            position_errors.append(source_bbox.position_error_ratio(recovered_bbox))

    text_recall = matched / len(source_texts) if source_texts else 1.0
    text_position_error = (
        sum(position_errors) / len(position_errors) if position_errors else 0.0
    )

    source_lines = [
        node for node in source.nodes if isinstance(node, ShapeNode) and node.shape_kind == "line"
    ]
    recovered_lines = [
        node
        for node in recovered.nodes
        if isinstance(node, ShapeNode) and node.shape_kind == "line"
    ]
    line_recall = (
        min(len(recovered_lines), len(source_lines)) / len(source_lines)
        if source_lines
        else 1.0
    )

    drawing_integrity_ok = _drawing_integrity_ok(source, recovered)
    asset_identity_preserved = _asset_identity_ok(source, recovered)
    similarity_score = _structural_similarity(
        text_recall=text_recall,
        text_position_error=text_position_error,
        line_recall=line_recall,
        drawing_integrity_ok=drawing_integrity_ok,
        asset_identity_preserved=asset_identity_preserved,
        source=source,
        recovered=recovered,
    )

    return SlideRecoveryMetrics(
        text_recall=text_recall,
        text_position_error=text_position_error,
        line_recall=line_recall,
        drawing_integrity_ok=drawing_integrity_ok,
        similarity_score=similarity_score,
        asset_identity_preserved=asset_identity_preserved,
    )


def _drawing_integrity_ok(source: RenderScene, recovered: RenderScene) -> bool:
    source_drawings = [node for node in source.nodes if isinstance(node, DrawingNode)]
    if not source_drawings:
        return True

    recovered_drawings = [node for node in recovered.nodes if isinstance(node, DrawingNode)]
    if len(recovered_drawings) < len(source_drawings):
        return False

    for drawing in recovered_drawings:
        if drawing.fit_mode != "contain":
            return False
        if drawing.crop_allowed:
            return False
    return True


def _asset_identity_ok(source: RenderScene, recovered: RenderScene) -> bool:
    def asset_keys(scene: RenderScene) -> set[str]:
        keys: set[str] = set()
        for node in scene.nodes:
            if isinstance(node, (ImageNode, DrawingNode)):
                uri = (node.storage_uri or "").strip()
                if uri:
                    keys.add(uri)
                if node.asset_id is not None:
                    keys.add(str(node.asset_id))
        return keys

    source_keys = asset_keys(source)
    if not source_keys:
        return True
    recovered_keys = asset_keys(recovered)
    return source_keys.issubset(recovered_keys)


def _structural_similarity(
    *,
    text_recall: float,
    text_position_error: float,
    line_recall: float,
    drawing_integrity_ok: bool,
    asset_identity_preserved: bool,
    source: RenderScene,
    recovered: RenderScene,
) -> float:
    geom_score = max(0.0, 1.0 - text_position_error / 0.05)
    node_ratio = min(len(recovered.nodes), len(source.nodes)) / max(len(source.nodes), 1)
    drawing_score = 1.0 if drawing_integrity_ok else 0.5
    asset_score = 1.0 if asset_identity_preserved else 0.6
    return (
        text_recall * 0.35
        + geom_score * 0.20
        + line_recall * 0.10
        + drawing_score * 0.15
        + asset_score * 0.10
        + node_ratio * 0.10
    )


def _merge_table_bbox(regions: list[RecoveredPageRegion]) -> NormalizedBox | None:
    cells = [region for region in regions if region.semantic_role == "table_cell"]
    if not cells:
        return None
    min_x = min(region.bbox.x for region in cells)
    min_y = min(region.bbox.y for region in cells)
    max_x = max(region.bbox.x + region.bbox.width for region in cells)
    max_y = max(region.bbox.y + region.bbox.height for region in cells)
    return NormalizedBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)
