"""Apply ImageTreatmentSpec → ImageDerivative and retarget RenderScene URIs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    AssetPathResolver,
)
from archium.application.visual.image_derivative_executor import ImageDerivativeExecutor
from archium.application.visual.image_processor import ImageProcessor
from archium.application.visual.image_style_matcher import DeckStyleMatchResult, ImageStyleMatcher
from archium.application.visual.image_treatment_spec_planner import ImageTreatmentSpecPlanner
from archium.config.settings import Settings, get_settings
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    ImageCropStrategy,
    ImageDerivative,
    ImageUnifyParams,
)
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderNode,
    RenderScene,
)
from archium.infrastructure.database.repositories import AssetRepository
from archium.infrastructure.storage.local_storage import LocalProjectStorage
from archium.logging import get_logger

logger = get_logger(__name__, operation="image_derivative_service")


@dataclass(frozen=True)
class ImageDerivativeApplyResult:
    scene: RenderScene
    derivatives: tuple[ImageDerivative, ...]
    skipped: int = 0
    deck_style: DeckStyleMatchResult | None = None


class ImageDerivativeService:
    """OriginalAsset → TreatmentSpec → Derivative → scene storage_uri rewrite."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        settings: Settings | None = None,
        planner: ImageTreatmentSpecPlanner | None = None,
        executor: ImageDerivativeExecutor | None = None,
        storage: LocalProjectStorage | None = None,
        resolver: AssetPathResolver | None = None,
        processor: ImageProcessor | None = None,
        style_matcher: ImageStyleMatcher | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._processor = processor or ImageProcessor()
        self._planner = planner or ImageTreatmentSpecPlanner(processor=self._processor)
        self._executor = executor or ImageDerivativeExecutor(storage=storage)
        self._storage = storage or LocalProjectStorage()
        self._resolver = resolver or AssetPathResolver()
        self._style_matcher = style_matcher or ImageStyleMatcher()
        self._assets = AssetRepository(session) if session is not None else None

    def apply_to_scene(
        self,
        scene: RenderScene,
        *,
        project_id: UUID,
        design_system: DesignSystem | None = None,
    ) -> ImageDerivativeApplyResult:
        if not getattr(self._settings, "image_derivatives_enabled", True):
            return ImageDerivativeApplyResult(scene=scene, derivatives=(), skipped=0)
        if not self._executor.is_available():
            return ImageDerivativeApplyResult(scene=scene, derivatives=(), skipped=0)

        layout = self._storage.ensure_project_layout(project_id)
        ctx = AssetPathResolveContext(
            project_id=project_id,
            project_storage_root=self._settings.project_storage_path,
            assets_dir=layout["assets"],
        )

        resolved = self._resolve_visual_nodes(scene, project_id=project_id, resolve_ctx=ctx)
        deck_style = self._match_deck_style(resolved, design_system=design_system)
        deck_unify = deck_style.unify if deck_style is not None else None

        derivatives: list[ImageDerivative] = []
        skipped = 0
        nodes: list[RenderNode] = []
        for node in scene.nodes:
            if not isinstance(node, (ImageNode, DrawingNode)):
                nodes.append(node)
                continue
            original_path = resolved.get(node.id)
            updated, derivative = self._process_node(
                node,
                project_id=project_id,
                design_system=design_system,
                resolve_ctx=ctx,
                original_path=original_path,
                deck_unify=deck_unify,
            )
            nodes.append(updated)
            if derivative is not None:
                derivatives.append(derivative)
            else:
                skipped += 1

        return ImageDerivativeApplyResult(
            scene=scene.model_copy(update={"nodes": nodes}),
            derivatives=tuple(derivatives),
            skipped=skipped,
            deck_style=deck_style,
        )

    def _match_deck_style(
        self,
        resolved: dict[str, Path],
        *,
        design_system: DesignSystem | None,
    ) -> DeckStyleMatchResult | None:
        if design_system is None:
            return None
        treatment = design_system.image_style.photo_treatment
        if treatment not in {PhotoTreatment.SUBTLE_UNIFY, PhotoTreatment.HISTORICAL}:
            return None
        paths = list(resolved.values())
        if not paths:
            return None
        result = self._style_matcher.match_deck(paths)
        logger.info("Deck style match: %s", result.rationale)
        return result

    def _resolve_visual_nodes(
        self,
        scene: RenderScene,
        *,
        project_id: UUID,
        resolve_ctx: AssetPathResolveContext,
    ) -> dict[str, Path]:
        resolved: dict[str, Path] = {}
        for node in scene.nodes:
            if not isinstance(node, (ImageNode, DrawingNode)):
                continue
            path = self._resolve_original_path(node, project_id=project_id, resolve_ctx=resolve_ctx)
            if path is not None:
                resolved[node.id] = path
        return resolved

    def _resolve_original_path(
        self,
        node: ImageNode | DrawingNode,
        *,
        project_id: UUID,
        resolve_ctx: AssetPathResolveContext,
    ) -> Path | None:
        asset = None
        if self._assets is not None and node.asset_id is not None:
            asset = self._assets.get_by_id(node.asset_id)
        original_uri = node.storage_uri or node.asset_path
        original_path = self._resolver.resolve(original_uri, resolve_ctx) if original_uri else None
        if original_path is None and asset is not None and asset.path:
            candidate = Path(asset.path)
            if not candidate.is_file():
                candidate = self._settings.project_storage_path / str(project_id) / asset.path
            original_path = candidate if candidate.is_file() else None
        if original_path is None or not original_path.is_file():
            return None
        return original_path

    def _process_node(
        self,
        node: ImageNode | DrawingNode,
        *,
        project_id: UUID,
        design_system: DesignSystem | None,
        resolve_ctx: AssetPathResolveContext,
        original_path: Path | None,
        deck_unify: ImageUnifyParams | None,
    ) -> tuple[ImageNode | DrawingNode, ImageDerivative | None]:
        asset = None
        if self._assets is not None and node.asset_id is not None:
            asset = self._assets.get_by_id(node.asset_id)

        if original_path is None:
            original_path = self._resolve_original_path(
                node, project_id=project_id, resolve_ctx=resolve_ctx
            )
        if original_path is None:
            logger.info("Skip derivative; unresolved original for node %s", node.id)
            return node, None

        classification = self._processor.classify_source(
            path=original_path,
            asset=asset,
            filename=asset.filename if asset is not None else original_path.name,
            tags=list(asset.tags) if asset is not None else None,
            description=asset.description if asset is not None else None,
        )
        role_hint = self._processor.focus_hint_from_semantic_role(
            getattr(node, "semantic_role", "") or node.id
        )
        tags = list(asset.tags) if asset is not None else []
        tag_hint = self._processor.focus_hint_from_tags(tags)
        focus_hint = role_hint or tag_hint

        spec = self._planner.plan_for_node(
            node,
            design_system=design_system,
            asset=asset,
            source_kind=classification.kind,
            deck_unify=deck_unify,
            focus_hint=focus_hint,
        )
        if spec is None or spec.mode.value == "none":
            return node, None

        if isinstance(node, ImageNode) and (
            spec.crop_strategy
            in {
                ImageCropStrategy.SUBJECT_HEURISTIC,
                ImageCropStrategy.SKYLINE_HEURISTIC,
            }
            or (spec.auto_subject_crop and spec.focal_point.source != "manual")
        ):
            hint = focus_hint
            if spec.crop_strategy == ImageCropStrategy.SKYLINE_HEURISTIC:
                hint = "skyline"
            spec = self._processor.enrich_spec_with_focus(spec, original_path, hint=hint)

        try:
            derivative = self._executor.execute(
                spec,
                project_id=project_id,
                original_path=original_path,
            )
        except Exception as exc:  # noqa: BLE001 — soft-fail; keep original URI
            logger.info("Derivative failed for %s: %s", node.id, exc)
            return node, None

        if derivative is None or not derivative.storage_uri:
            return node, None

        return (
            node.model_copy(
                update={
                    "storage_uri": derivative.storage_uri,
                    "asset_path": derivative.storage_uri,
                }
            ),
            derivative,
        )
