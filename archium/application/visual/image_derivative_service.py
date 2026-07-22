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
from archium.application.visual.image_treatment_spec_planner import ImageTreatmentSpecPlanner
from archium.config.settings import Settings, get_settings
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.image_derivative import ImageDerivative
from archium.domain.visual.render_scene import (
    DrawingNode,
    ImageNode,
    RenderScene,
    ShapeNode,
    TextNode,
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
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._planner = planner or ImageTreatmentSpecPlanner()
        self._executor = executor or ImageDerivativeExecutor(storage=storage)
        self._storage = storage or LocalProjectStorage()
        self._resolver = resolver or AssetPathResolver()
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

        derivatives: list[ImageDerivative] = []
        skipped = 0
        nodes: list[TextNode | ImageNode | DrawingNode] = []
        for node in scene.nodes:
            if not isinstance(node, (ImageNode, DrawingNode)):
                nodes.append(node)
                continue
            updated, derivative = self._process_node(
                node,
                project_id=project_id,
                design_system=design_system,
                resolve_ctx=ctx,
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
        )

    def _process_node(
        self,
        node: ImageNode | DrawingNode,
        *,
        project_id: UUID,
        design_system: DesignSystem | None,
        resolve_ctx: AssetPathResolveContext,
    ) -> tuple[ImageNode | DrawingNode, ImageDerivative | None]:
        asset = None
        if self._assets is not None and node.asset_id is not None:
            asset = self._assets.get_by_id(node.asset_id)
        spec = self._planner.plan_for_node(
            node,
            design_system=design_system,
            asset=asset,
        )
        if spec is None or spec.mode.value == "none":
            return node, None

        original_uri = node.storage_uri or node.asset_path
        original_path = self._resolver.resolve(original_uri, resolve_ctx) if original_uri else None
        if original_path is None and asset is not None and asset.path:
            candidate = Path(asset.path)
            if not candidate.is_file():
                candidate = self._settings.project_storage_path / str(project_id) / asset.path
            original_path = candidate if candidate.is_file() else None
        if original_path is None or not original_path.is_file():
            logger.info("Skip derivative; unresolved original for node %s", node.id)
            return node, None

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
