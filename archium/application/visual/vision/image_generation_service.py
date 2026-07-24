"""Vision Image Generation Service — compile → generate → optional Asset persist."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.visual.vision.diagram_composer import (
    DiagramComposeRequest,
    VisionDiagramComposer,
    supports_diagram_compose,
)
from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual.vision_generation import (
    GenerationSpec,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationContext,
    VisionGenerationResult,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository
from archium.infrastructure.storage.local_storage import LocalProjectStorage
from archium.infrastructure.vision_gen.base import (
    GeneratedImageBytes,
    VisionImageGenerator,
)
from archium.infrastructure.vision_gen.factory import build_vision_image_generator
from archium.logging import get_logger

logger = get_logger(__name__, operation="vision_image_generation")


class VisionImageGenerationService:
    """Visual-seat service: Prompt Compiler + pluggable generator + Asset library."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        settings: Settings | None = None,
        compiler: VisionPromptCompiler | None = None,
        generator: VisionImageGenerator | None = None,
        storage: LocalProjectStorage | None = None,
        diagram_composer: VisionDiagramComposer | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._compiler = compiler or VisionPromptCompiler()
        self._generator = generator or build_vision_image_generator(self._settings)
        self._storage = storage or LocalProjectStorage(settings=self._settings)
        self._composer = diagram_composer or VisionDiagramComposer()
        self._assets = AssetRepository(session) if session is not None else None

    def compile(
        self,
        request: ImageRequest,
        *,
        context: VisionGenerationContext | None = None,
    ) -> GenerationSpec:
        return self._compiler.compile(request, context=context)

    def generate(
        self,
        request: ImageRequest,
        *,
        context: VisionGenerationContext | None = None,
        project_id: UUID | None = None,
        persist_asset: bool = False,
    ) -> VisionGenerationResult:
        """Generate illustrative pixels. Never claims to be site evidence."""
        if request.asset_policy not in {
            VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            VisionAssetPolicy.FORBIDDEN_FOR_EVIDENCE,
        }:
            raise WorkflowError("Vision Engine 仅支持示意类资产策略（illustrative_only）。")

        spec = self.compile(request, context=context)
        try:
            payload = self._produce_pixels(request, spec)
        except Exception as exc:  # pragma: no cover - provider-specific
            logger.warning("Vision generation failed: %s", exc)
            return VisionGenerationResult(
                success=False,
                spec=spec,
                error=str(exc),
                provider=getattr(self._generator, "provider", ""),
                model=getattr(self._generator, "model", ""),
            )

        if payload is None:
            return VisionGenerationResult(
                success=False,
                spec=spec,
                error="image generator unavailable",
                provider=getattr(self._generator, "provider", ""),
                model=getattr(self._generator, "model", ""),
            )

        storage_path: str | None = None
        asset_id: UUID | None = None
        if persist_asset:
            if project_id is None:
                raise WorkflowError("persist_asset=True 时必须提供 project_id。")
            storage_path, asset_id = self._persist(
                project_id=project_id,
                spec=spec,
                data=payload.data,
                mime_type=payload.mime_type,
                provider=payload.provider,
                model=payload.model,
            )

        return VisionGenerationResult(
            success=True,
            spec=spec,
            storage_path=storage_path,
            asset_id=asset_id,
            mime_type=payload.mime_type,
            provider=payload.provider,
            model=payload.model,
            illustrative=True,
        )

    def _produce_pixels(
        self,
        request: ImageRequest,
        spec: GenerationSpec,
    ) -> GeneratedImageBytes | None:
        """Prefer base+overlay compose for diagram types; else pluggable generator."""
        compose_mode = bool(spec.metadata.get("compose_mode")) and bool(request.base_image_path)
        if (
            compose_mode
            and request.base_image_path
            and supports_diagram_compose(request.image_type)
            and self._composer.is_available()
        ):
            cues = tuple(
                str(item)
                for item in (spec.metadata.get("overlay_cues") or request.overlay_cues or [])
                if str(item).strip()
            )
            data = self._composer.compose(
                DiagramComposeRequest(
                    base_image_path=request.base_image_path,
                    width=spec.width,
                    height=spec.height,
                    image_type=request.image_type,
                    subject=request.subject,
                    overlay_cues=cues,
                    prompt_hash=spec.prompt_hash,
                    label="Archium Vision · base + overlay (illustrative)",
                )
            )
            return GeneratedImageBytes(
                data=data,
                mime_type="image/png",
                provider="diagram_composer",
                model="pillow_overlay_v02",
            )

        if not self._generator.is_available():
            return None
        return self._generator.generate(spec)

    def generate_for_intent(
        self,
        *,
        request: ImageRequest,
        project_id: UUID,
        slide_title: str = "",
        slide_message: str = "",
        page_archetype: str = "",
        project_type: str = "",
        audience: str = "",
        persist_asset: bool = True,
    ) -> VisionGenerationResult:
        """Convenience: SlideSpec/VisualIntent fields → generation."""
        context = VisionGenerationContext(
            project_type=project_type,
            audience=audience,
            page_title=slide_title,
            page_message=slide_message,
            page_archetype=page_archetype,
            project_phase="concept",
        )
        return self.generate(
            request,
            context=context,
            project_id=project_id,
            persist_asset=persist_asset,
        )

    def _persist(
        self,
        *,
        project_id: UUID,
        spec: GenerationSpec,
        data: bytes,
        mime_type: str,
        provider: str,
        model: str,
    ) -> tuple[str, UUID | None]:
        layout = self._storage.ensure_project_layout(project_id)
        vision_dir = layout["assets"] / "vision_generated"
        vision_dir.mkdir(parents=True, exist_ok=True)
        ext = ".png" if "png" in mime_type else ".jpg"
        filename = f"vision_{spec.image_type.value}_{spec.prompt_hash}{ext}"
        destination = vision_dir / filename
        destination.write_bytes(data)
        relative = str(Path("assets") / "vision_generated" / filename)

        asset_id: UUID | None = None
        if self._assets is not None:
            asset = Asset(
                id=uuid4(),
                project_id=project_id,
                filename=filename,
                path=str(destination.resolve()),
                asset_type=AssetType.PHOTO,
                description=f"Vision Engine · {spec.image_type.value} · illustrative",
                tags=["ai_generated", "illustrative", spec.image_type.value, "vision_engine"],
                metadata={
                    "origin": "ai_generated",
                    "illustrative": True,
                    "asset_policy": spec.asset_policy.value,
                    "prompt_hash": spec.prompt_hash,
                    "prompt": spec.prompt[:2000],
                    "negative_prompt": spec.negative_prompt[:1000],
                    "provider": provider,
                    "model": model,
                    "image_type": spec.image_type.value,
                    "style": spec.style,
                    "rationale": list(spec.rationale),
                    "compose_mode": bool(spec.metadata.get("compose_mode")),
                    "base_image_path": spec.metadata.get("base_image_path"),
                },
            )
            saved = self._assets.create(asset)
            asset_id = saved.id
        return relative, asset_id
