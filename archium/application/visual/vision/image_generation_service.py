"""Vision Image Generation Service — compile → generate/edit → QA → optional Asset."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.visual.image_derivative_executor import ImageDerivativeExecutor
from archium.application.visual.vision.conditioned_editor import (
    ConditionedEditRequest,
    VisionConditionedEditor,
    soft_harmonize_png,
)
from archium.application.visual.vision.diagram_composer import (
    DiagramComposeRequest,
    VisionDiagramComposer,
    supports_diagram_compose,
)
from archium.application.visual.vision.image_evaluator import VisionImageEvaluator
from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType
from archium.domain.visual.image_derivative import (
    ImageAssetClass,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    default_presentation_unify_params,
)
from archium.domain.visual.vision_generation import (
    GenerationSpec,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationContext,
    VisionGenerationMode,
    VisionGenerationResult,
    VisionInputEvaluation,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository
from archium.infrastructure.database.visual_repositories import VisualIntentRepository
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
        conditioned_editor: VisionConditionedEditor | None = None,
        evaluator: VisionImageEvaluator | None = None,
        derivative_executor: ImageDerivativeExecutor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._compiler = compiler or VisionPromptCompiler()
        self._generator = generator or build_vision_image_generator(self._settings)
        self._storage = storage or LocalProjectStorage(settings=self._settings)
        self._composer = diagram_composer or VisionDiagramComposer()
        self._editor = conditioned_editor or VisionConditionedEditor()
        self._evaluator = evaluator or VisionImageEvaluator()
        self._derivative = derivative_executor or ImageDerivativeExecutor(storage=self._storage)
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

        if request.mode in {
            VisionGenerationMode.EDIT_FROM_PHOTO,
            VisionGenerationMode.EDIT_FROM_DRAWING,
        } and not request.base_image_path:
            raise WorkflowError("条件改图模式必须提供 base_image_path。")

        input_eval: VisionInputEvaluation | None = None
        if request.base_image_path:
            input_eval = self._evaluator.evaluate_base_image(request.base_image_path)
            if input_eval.blocking:
                spec = self.compile(request, context=context)
                return VisionGenerationResult(
                    success=False,
                    spec=spec,
                    error="; ".join(input_eval.warnings) or "base image rejected",
                    input_evaluation=input_eval,
                    provider="",
                    model="",
                )

        spec = self.compile(request, context=context)
        if input_eval is not None and input_eval.warnings:
            spec.metadata = {
                **spec.metadata,
                "input_qa_warnings": list(input_eval.warnings),
                "input_qa": input_eval.model_dump(mode="json"),
            }

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
                input_evaluation=input_eval,
            )

        if payload is None:
            return VisionGenerationResult(
                success=False,
                spec=spec,
                error="image generator unavailable",
                provider=getattr(self._generator, "provider", ""),
                model=getattr(self._generator, "model", ""),
                input_evaluation=input_eval,
            )

        harmonized = False
        data = payload.data
        mime_type = payload.mime_type
        # Prefer formal ImageDerivative PRESENTATION_UNIFY after persist; soft
        # harmonize only when we will not run the derivative pipeline.
        use_derivative = (
            request.harmonize_output
            and persist_asset
            and project_id is not None
            and self._derivative.is_available()
        )
        if request.harmonize_output and not use_derivative and "png" in mime_type:
            try:
                data = soft_harmonize_png(data)
                harmonized = True
            except Exception as exc:  # pragma: no cover
                logger.info("Vision soft harmonize skipped: %s", exc)

        storage_path: str | None = None
        asset_id: UUID | None = None
        if persist_asset:
            if project_id is None:
                raise WorkflowError("persist_asset=True 时必须提供 project_id。")
            storage_path, asset_id = self._persist(
                project_id=project_id,
                spec=spec,
                data=data,
                mime_type=mime_type,
                provider=payload.provider,
                model=payload.model,
                harmonized=harmonized,
                input_evaluation=input_eval,
            )
            if use_derivative and storage_path:
                layout = self._storage.ensure_project_layout(project_id)
                original = layout["root"] / Path(storage_path)
                if not original.is_file():
                    original = Path(storage_path)
                applied = self._apply_presentation_unify(
                    project_id=project_id,
                    asset_id=asset_id or uuid4(),
                    original_path=original,
                    spec=spec,
                )
                if applied is not None:
                    new_path, mime_type, new_asset_id = applied
                    storage_path = new_path
                    harmonized = True
                    if asset_id is not None and new_asset_id is not None:
                        asset_id = new_asset_id

        return VisionGenerationResult(
            success=True,
            spec=spec,
            storage_path=storage_path,
            asset_id=asset_id,
            mime_type=mime_type,
            provider=payload.provider,
            model=payload.model,
            illustrative=True,
            input_evaluation=input_eval,
            harmonized=harmonized,
        )

    def _produce_pixels(
        self,
        request: ImageRequest,
        spec: GenerationSpec,
    ) -> GeneratedImageBytes | None:
        """Edit / compose / generate — prefer conditioned paths when requested."""
        if request.mode in {
            VisionGenerationMode.EDIT_FROM_PHOTO,
            VisionGenerationMode.EDIT_FROM_DRAWING,
        }:
            return self._produce_edit(request, spec)

        compose_mode = bool(spec.metadata.get("compose_mode")) and bool(request.base_image_path)
        if (
            compose_mode
            and request.base_image_path
            and supports_diagram_compose(request.image_type)
            and self._composer.is_available()
        ):
            cues = tuple(
                str(item)
                for item in cast(
                    Sequence[object],
                    spec.metadata.get("overlay_cues") or request.overlay_cues or (),
                )
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

    def _produce_edit(
        self,
        request: ImageRequest,
        spec: GenerationSpec,
    ) -> GeneratedImageBytes | None:
        assert request.base_image_path
        # Prefer provider edit when available; otherwise Pillow conditioned editor.
        edit_fn = getattr(self._generator, "edit", None)
        if callable(edit_fn) and self._generator.is_available():
            try:
                return cast(
                    GeneratedImageBytes,
                    edit_fn(spec, base_image_path=request.base_image_path),
                )
            except Exception as exc:
                logger.info("Provider image edit unavailable, using local editor: %s", exc)

        if not self._editor.is_available():
            return None
        cues = tuple(
            str(item)
            for item in cast(
                Sequence[object],
                spec.metadata.get("overlay_cues") or request.overlay_cues or (),
            )
            if str(item).strip()
        )
        data = self._editor.edit(
            ConditionedEditRequest(
                base_image_path=request.base_image_path,
                width=spec.width,
                height=spec.height,
                subject=request.subject,
                mode=request.mode,
                style=spec.style,
                prompt_hash=spec.prompt_hash,
                overlay_cues=cues,
            )
        )
        return GeneratedImageBytes(
            data=data,
            mime_type="image/png",
            provider=self._editor.provider,
            model=self._editor.model,
        )

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

    def fulfill_intent_image_request(
        self,
        intent: VisualIntent,
        *,
        project_id: UUID,
        slide_title: str = "",
        slide_message: str = "",
        page_archetype: str = "",
        persist: bool = True,
    ) -> tuple[VisualIntent, list[str]]:
        """Fulfill ``image_request`` into an illustrative Asset when hero is empty.

        Non-blocking: generation failures become warnings; never claims evidence.
        """
        warnings: list[str] = []
        if intent.image_request is None or intent.hero_asset_id is not None:
            return intent, warnings
        if not self._settings.vision_image_generation_enabled:
            return intent, warnings
        if not self._settings.vision_auto_fulfill_image_requests:
            return intent, warnings

        archetype = page_archetype
        if not archetype and intent.page_archetype is not None:
            archetype = intent.page_archetype.value

        result = self.generate_for_intent(
            request=intent.image_request,
            project_id=project_id,
            slide_title=slide_title,
            slide_message=slide_message,
            page_archetype=archetype,
            persist_asset=True,
        )
        if not result.success or result.asset_id is None:
            warnings.append(result.error or "示意出图失败，已保留 image_request。")
            return intent, warnings

        updated = intent.model_copy(update={"hero_asset_id": result.asset_id})
        if persist and self._session is not None:
            updated = VisualIntentRepository(self._session).save(updated)
        return updated, warnings

    def _persist(
        self,
        *,
        project_id: UUID,
        spec: GenerationSpec,
        data: bytes,
        mime_type: str,
        provider: str,
        model: str,
        harmonized: bool = False,
        input_evaluation: VisionInputEvaluation | None = None,
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
                    "edit_mode": bool(spec.metadata.get("edit_mode")),
                    "generation_mode": spec.metadata.get("generation_mode"),
                    "base_image_path": spec.metadata.get("base_image_path"),
                    "harmonized": harmonized,
                    "input_qa_warnings": (
                        list(input_evaluation.warnings) if input_evaluation else []
                    ),
                },
            )
            saved = self._assets.create(asset)
            asset_id = saved.id
        return relative, asset_id

    def _apply_presentation_unify(
        self,
        *,
        project_id: UUID,
        asset_id: UUID,
        original_path: Path,
        spec: GenerationSpec,
    ) -> tuple[str, str, UUID | None] | None:
        """Run ImageDerivative PRESENTATION_UNIFY; return (rel_path, mime, asset_id)."""
        if not original_path.is_file():
            return None
        treatment = ImageTreatmentSpec(
            original_asset_id=asset_id,
            asset_class=ImageAssetClass.PRESENTATION,
            mode=ImageTreatmentMode.PRESENTATION_UNIFY,
            unify=default_presentation_unify_params(),
            rationale="vision_engine_post_harmonize",
        )
        try:
            derivative = self._derivative.execute(
                treatment,
                project_id=project_id,
                original_path=original_path,
            )
        except Exception as exc:  # pragma: no cover
            logger.info("Vision derivative unify failed: %s", exc)
            return None
        if derivative is None or not derivative.storage_uri:
            return None

        layout = self._storage.ensure_project_layout(project_id)
        prefix = f"storage://projects/{project_id}/"
        uri = derivative.storage_uri
        if not uri.startswith(prefix):
            return None
        der_path = layout["root"] / uri[len(prefix) :]
        if not der_path.is_file():
            return None

        vision_dir = layout["assets"] / "vision_generated"
        vision_dir.mkdir(parents=True, exist_ok=True)
        final_name = f"vision_{spec.image_type.value}_{spec.prompt_hash}_harmonized.jpg"
        final_path = vision_dir / final_name
        final_path.write_bytes(der_path.read_bytes())
        relative = str(Path("assets") / "vision_generated" / final_name)

        if self._assets is not None:
            asset = self._assets.get_by_id(asset_id)
            if asset is not None:
                meta = dict(asset.metadata or {})
                meta.update(
                    {
                        "harmonized": True,
                        "harmonize_pipeline": "image_derivative_presentation_unify",
                        "derivative_params_hash": derivative.params_hash,
                        "derivative_storage_uri": derivative.storage_uri,
                        "original_vision_path": str(original_path),
                    }
                )
                updated = asset.model_copy(
                    update={
                        "path": str(final_path.resolve()),
                        "filename": final_name,
                        "metadata": meta,
                    }
                )
                saved = self._assets.update(updated)
                return relative, "image/jpeg", saved.id
        return relative, "image/jpeg", asset_id
