"""Map ConceptDirection structured fields to Vision Engine seeds."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationMode,
    VisionStylePreset,
)
from archium.domain.visual.visual_concept_brief import VisualConceptBrief

_STYLE_ALIASES: dict[str, VisionStylePreset] = {
    "concept sketch": VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
    "competition concept sketch": VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
    "marker sketch": VisionStylePreset.MARKER_SKETCH,
    "soft atmosphere": VisionStylePreset.SOFT_ATMOSPHERE,
    "soft sketch": VisionStylePreset.MARKER_SKETCH,
    "watercolor note": VisionStylePreset.WATERCOLOR_NOTE,
    "watercolor": VisionStylePreset.WATERCOLOR_NOTE,
    "axonometric diagram": VisionStylePreset.AXONOMETRIC_DIAGRAM,
    "flat analytical diagram": VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
    "pencil sketch": VisionStylePreset.PENCIL_SKETCH,
}


def preview_compiled_prompt_for_direction(direction: ConceptDirection) -> str:
    """Compile Vision prompt from direction seed without persisting a brief."""
    from archium.application.visual.vision.prompt_compiler import VisionPromptCompiler

    request = image_request_from_concept_direction(direction)
    spec = VisionPromptCompiler().compile(request, direction=direction)
    return spec.prompt


def direction_has_visual_seed(direction: ConceptDirection) -> bool:
    """True when ConceptDirection carries a direct image generation seed."""
    vp = direction.visual_prompt
    return vp is not None and bool(vp.image_prompt.strip())


def resolve_style_from_visual_prompt(raw: str) -> VisionStylePreset | str:
    text = (raw or "").strip().lower()
    if not text:
        return VisionStylePreset.COMPETITION_CONCEPT_SKETCH
    if text in {item.value for item in VisionStylePreset}:
        return VisionStylePreset(text)
    for alias, preset in _STYLE_ALIASES.items():
        if alias in text or text in alias:
            return preset
    return VisionStylePreset.COMPETITION_CONCEPT_SKETCH


def resolve_image_type_from_camera(camera: str, *, style: str = "") -> ArchitectureImageType:
    text = f"{camera} {style}".lower()
    if any(token in text for token in ("axonometric", "diagram", "site plan", "分析")):
        return ArchitectureImageType.SITE_DIAGRAM
    if any(token in text for token in ("atmosphere", "eye-level", "street", "氛围")):
        return ArchitectureImageType.ATMOSPHERE_IMAGE
    if any(token in text for token in ("section", "剖面")):
        return ArchitectureImageType.SECTION_ILLUSTRATION
    if any(token in text for token in ("material", "材料")):
        return ArchitectureImageType.MATERIAL_STUDY
    if any(token in text for token in ("sketch note", "笔记")):
        return ArchitectureImageType.SKETCH_NOTE
    return ArchitectureImageType.CONCEPT_SKETCH


def build_direction_seed_elements(direction: ConceptDirection) -> list[str]:
    elements: list[str] = []
    vp = direction.visual_prompt
    if vp is not None and vp.camera.strip():
        elements.append(f"camera/view: {vp.camera.strip()}")
    for label, value in (
        ("spatial strategy", direction.spatial_strategy),
        ("form language", direction.formal_language),
        ("material strategy", direction.material_strategy),
    ):
        if value.strip():
            elements.append(f"{label}: {value.strip()}")
    for ref in direction.reference_dna[:4]:
        if ref.strip():
            elements.append(f"reference dna: {ref.strip()}")
    if direction.differentiator.strip():
        elements.append(f"differentiator: {direction.differentiator.strip()}")
    return elements


def apply_direction_seed_to_request(
    request: ImageRequest,
    direction: ConceptDirection,
) -> ImageRequest:
    """Enrich ImageRequest from ConceptDirection without replacing explicit brief fields."""
    if not direction_has_visual_seed(direction) and not _has_structured_spatial_fields(direction):
        return request

    vp = direction.visual_prompt or ConceptVisualPrompt()
    style = resolve_style_from_visual_prompt(vp.style) if vp.style.strip() else request.style
    image_type = request.image_type
    if vp.camera.strip() or vp.style.strip():
        image_type = resolve_image_type_from_camera(vp.camera, style=vp.style)

    subject = request.subject.strip() or direction.title
    if vp.image_prompt.strip():
        subject = vp.image_prompt.strip()[:500]

    purpose_parts = [request.purpose.strip()]
    if direction.spatial_strategy.strip() and direction.spatial_strategy not in request.purpose:
        purpose_parts.append(direction.spatial_strategy.strip())
    if direction.experience_focus.strip():
        purpose_parts.append(direction.experience_focus.strip())
    purpose = " ".join(part for part in purpose_parts if part)[:500]

    elements = list(dict.fromkeys([*build_direction_seed_elements(direction), *request.elements]))[:12]
    return request.model_copy(
        update={
            "image_type": image_type,
            "subject": subject,
            "purpose": purpose or request.purpose,
            "style": style,
            "elements": elements,
        }
    )


def image_request_from_concept_direction(direction: ConceptDirection) -> ImageRequest:
    """Build ImageRequest directly from a concept direction seed."""
    vp = direction.visual_prompt or ConceptVisualPrompt()
    style = resolve_style_from_visual_prompt(vp.style)
    image_type = resolve_image_type_from_camera(vp.camera, style=vp.style)
    subject = vp.image_prompt.strip()[:500] if vp.image_prompt.strip() else direction.title
    purpose_parts = [
        direction.spatial_strategy,
        direction.formal_language,
        direction.experience_focus,
    ]
    purpose = " ".join(part.strip() for part in purpose_parts if part.strip())[:500]
    return ImageRequest(
        image_type=image_type,
        subject=subject,
        purpose=purpose or "concept visual exploration",
        style=style,
        elements=build_direction_seed_elements(direction),
        avoid=[
            "luxury commercial real-estate rendering",
            "photorealistic site survey photo presented as evidence",
        ],
        asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
        mode=VisionGenerationMode.TEXT_TO_IMAGE,
    )


def visual_concept_brief_from_direction_seed(
    mission: ProjectMission,
    direction: ConceptDirection,
) -> VisualConceptBrief:
    """Text-first brief derived from direction seed (no LLM)."""
    vp = direction.visual_prompt
    assert vp is not None and vp.image_prompt.strip()
    style = resolve_style_from_visual_prompt(vp.style)
    image_type = resolve_image_type_from_camera(vp.camera, style=vp.style)
    composition = " · ".join(
        part.strip()
        for part in (
            direction.spatial_strategy,
            direction.spatial_idea,
            vp.camera,
        )
        if part and part.strip()
    )[:500]
    atmosphere = " · ".join(
        part.strip()
        for part in (
            direction.formal_language,
            direction.material_strategy,
            direction.experience_focus,
        )
        if part and part.strip()
    )[:500]
    return VisualConceptBrief(
        project_id=mission.project_id,
        mission_id=mission.id,
        concept_direction_id=direction.id,
        title=(direction.title or "概念视觉")[:200],
        composition_intent=composition,
        atmosphere=atmosphere,
        diagram_intent=direction.spatial_strategy[:500] if direction.spatial_strategy else "",
        image_type=image_type,
        style_preset=style,
        subject=vp.image_prompt.strip()[:500],
        elements=build_direction_seed_elements(direction)[:12],
        avoid=[
            "luxury commercial real-estate rendering",
            "photorealistic site survey photo presented as evidence",
        ],
        status="draft",
        extra_json={"seed_source": "concept_direction.visual_prompt"},
    )


def _has_structured_spatial_fields(direction: ConceptDirection) -> bool:
    return bool(
        direction.spatial_strategy.strip()
        or direction.formal_language.strip()
        or direction.material_strategy.strip()
    )
