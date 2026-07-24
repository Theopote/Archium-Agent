"""Vision Engine domain — architectural image generation intents (not Midjourney chat)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class ArchitectureImageType(StrEnum):
    """Product-facing generation categories (Vision Engine v0.1+)."""

    CONCEPT_SKETCH = "concept_sketch"
    SITE_DIAGRAM = "site_diagram"
    FLOW_DIAGRAM = "flow_diagram"
    SECTION_ILLUSTRATION = "section_illustration"
    ATMOSPHERE_IMAGE = "atmosphere_image"
    MATERIAL_STUDY = "material_study"
    PRESENTATION_ILLUSTRATION = "presentation_illustration"
    SKETCH_NOTE = "sketch_note"


class VisionAssetPolicy(StrEnum):
    """How generated pixels may be used in the deck."""

    ILLUSTRATIVE_ONLY = "illustrative_only"
    """May fill non-evidence illustration / atmosphere / concept slots."""

    FORBIDDEN_FOR_EVIDENCE = "forbidden_for_evidence"
    """Alias of illustrative_only — never silently bind as site photo / drawing evidence."""


class VisionStylePreset(StrEnum):
    """High-level style packs (Prompt Compiler expands these)."""

    COMPETITION_CONCEPT_SKETCH = "competition_concept_sketch"
    MARKER_SKETCH = "marker_sketch"
    PENCIL_SKETCH = "pencil_sketch"
    AXONOMETRIC_DIAGRAM = "axonometric_diagram"
    FLAT_ANALYTICAL_DIAGRAM = "flat_analytical_diagram"
    SOFT_ATMOSPHERE = "soft_atmosphere"
    WATERCOLOR_NOTE = "watercolor_note"


class VisionGenerationMode(StrEnum):
    """How pixels are produced (Vision Engine v0.3)."""

    TEXT_TO_IMAGE = "text_to_image"
    """Pure generation from compiled prompt."""

    EDIT_FROM_PHOTO = "edit_from_photo"
    """Conditioned edit / style transfer from a user photo (always illustrative)."""

    EDIT_FROM_DRAWING = "edit_from_drawing"
    """Conditioned edit from a plan/drawing base (distinct from diagram compose overlay)."""


class ImageRequest(DomainModel):
    """Declarative request attached to VisualIntent / Design Brief (no pixels)."""

    image_type: ArchitectureImageType = ArchitectureImageType.PRESENTATION_ILLUSTRATION
    subject: str = Field(min_length=1, max_length=500)
    purpose: str = Field(default="", max_length=500)
    style: VisionStylePreset | str | None = Field(
        default=None,
        description="None resolves from VisionStylePresetRegistry type template (v0.2).",
    )
    elements: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    asset_policy: VisionAssetPolicy = VisionAssetPolicy.ILLUSTRATIVE_ONLY
    aspect_ratio: str = Field(default="16:9", max_length=16)
    width: int = Field(default=1280, ge=256, le=4096)
    height: int = Field(default=720, ge=256, le=4096)
    # v0.2 diagram compose — user site plan / drawing as base (never treated as evidence output).
    base_image_path: str | None = Field(default=None, max_length=1024)
    overlay_cues: list[str] = Field(default_factory=list)
    # v0.3 conditioned edit + post pipeline
    mode: VisionGenerationMode = VisionGenerationMode.TEXT_TO_IMAGE
    harmonize_output: bool = Field(
        default=True,
        description="Apply soft presentation unify (Derivative-spirit) before persist.",
    )
    denoising_strength: float | None = Field(
        default=None,
        ge=0.05,
        le=1.0,
        description="img2img strength for local_sd / edit backends (None = provider default).",
    )


class VisionInputEvaluation(DomainModel):
    """Base-image QA before conditioned edit (reuse photo sharpness / exposure)."""

    sharpness_passed: bool | None = None
    exposure_passed: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking: bool = False
    checks: list[dict[str, object]] = Field(default_factory=list)


class VisionGenerationContext(DomainModel):
    """Architectural / presentation context fed into Prompt Compiler."""

    project_type: str = ""
    project_phase: str = "concept"
    audience: str = ""
    page_title: str = ""
    page_message: str = ""
    page_archetype: str = ""
    design_brief_summary: str = ""
    locale: str = "zh-CN"


class GenerationSpec(DomainModel):
    """Compiled provider-agnostic generation brief (Archium barrier)."""

    image_type: ArchitectureImageType
    style: str
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    width: int = Field(ge=256, le=4096)
    height: int = Field(ge=256, le=4096)
    asset_policy: VisionAssetPolicy = VisionAssetPolicy.ILLUSTRATIVE_ONLY
    rationale: list[str] = Field(default_factory=list)
    prompt_hash: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class VisionGenerationResult(DomainModel):
    """Outcome of a generation attempt (bytes may be persisted separately)."""

    success: bool
    spec: GenerationSpec
    storage_path: str | None = None
    asset_id: UUID | None = None
    mime_type: str = "image/png"
    provider: str = ""
    model: str = ""
    error: str | None = None
    illustrative: bool = True
    input_evaluation: VisionInputEvaluation | None = None
    harmonized: bool = False
