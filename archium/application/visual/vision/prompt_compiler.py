"""Prompt Compiler - architectural semantics to GenerationSpec (Vision Engine barrier)."""

from __future__ import annotations

import hashlib
import re

from archium.application.visual.vision.style_preset_registry import (
    DEFAULT_STYLE_REGISTRY,
    VisionStylePresetRegistry,
)
from archium.domain.visual.vision_generation import (
    GenerationSpec,
    ImageRequest,
    VisionAssetPolicy,
    VisionGenerationContext,
    VisionGenerationMode,
    VisionStylePreset,
)


_DEFAULT_AVOID = (
    "luxury commercial real-estate rendering",
    "photorealistic site survey photo presented as evidence",
    "unrealistic futuristic megastructure",
    "stock business people handshake",
    "watermark, logo spam, illegible text soup",
)


class VisionPromptCompiler:
    """Compile ImageRequest + context into a provider-agnostic GenerationSpec."""

    def __init__(self, registry: VisionStylePresetRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_STYLE_REGISTRY

    def compile(
        self,
        request: ImageRequest,
        *,
        context: VisionGenerationContext | None = None,
    ) -> GenerationSpec:
        ctx = context or VisionGenerationContext()
        template = self._registry.get_type_template(request.image_type)

        if request.style is None or (isinstance(request.style, str) and not request.style.strip()):
            style_key = template.default_style.value
        elif isinstance(request.style, VisionStylePreset):
            style_key = request.style.value
        else:
            style_key = str(request.style).strip()

        style_prose = self._registry.style_prose(style_key)
        purpose = (request.purpose or "").strip() or template.purpose

        elements = [item.strip() for item in request.elements if item.strip()]
        for default in template.default_elements:
            if default not in elements and len(elements) < 8:
                elements.append(default)
        if ctx.page_title and ctx.page_title not in elements:
            elements.append(f"page theme: {ctx.page_title}")
        if ctx.page_message and len(elements) < 8:
            elements.append(f"message cue: {ctx.page_message[:120]}")

        overlay_cues = [cue.strip() for cue in request.overlay_cues if cue.strip()]
        for cue in overlay_cues:
            if cue not in elements and len(elements) < 10:
                elements.append(f"overlay: {cue}")

        avoid = list(
            dict.fromkeys(
                [
                    *request.avoid,
                    *_DEFAULT_AVOID,
                    *self._registry.style_extra_avoid(style_key),
                ]
            )
        )
        if request.asset_policy in {
            VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            VisionAssetPolicy.FORBIDDEN_FOR_EVIDENCE,
        }:
            avoid.append("do not resemble an unverified site photograph used as project evidence")

        prompt_parts = [
            "Architectural visualization for a professional design presentation.",
            f"Image category: {request.image_type.value.replace('_', ' ')}.",
            f"Purpose: {purpose}.",
            f"Subject: {request.subject.strip()}.",
            f"Style: {style_prose}.",
        ]
        if ctx.project_type:
            prompt_parts.append(f"Project type: {ctx.project_type}.")
        if ctx.project_phase:
            prompt_parts.append(f"Design phase: {ctx.project_phase}.")
        if ctx.audience:
            prompt_parts.append(f"Audience: {ctx.audience}.")
        if ctx.page_archetype:
            prompt_parts.append(f"Page archetype: {ctx.page_archetype}.")
        if ctx.design_brief_summary:
            prompt_parts.append(f"Brief: {ctx.design_brief_summary[:240]}.")
        if elements:
            prompt_parts.append("Include: " + "; ".join(elements[:8]) + ".")

        compose_mode = (
            request.mode == VisionGenerationMode.TEXT_TO_IMAGE
            and bool(request.base_image_path)
            and self._registry.supports_base_overlay(request.image_type)
        )
        edit_mode = request.mode in {
            VisionGenerationMode.EDIT_FROM_PHOTO,
            VisionGenerationMode.EDIT_FROM_DRAWING,
        }
        if compose_mode:
            prompt_parts.append(
                "Composition mode: analytical overlay on an existing site / plan base - "
                "favor clear arrows, zones, and strategy labels over inventing a new site."
            )
            avoid.append("replace or invent a fake cadastral survey photo as the base")
        if edit_mode:
            kind = (
                "photograph"
                if request.mode == VisionGenerationMode.EDIT_FROM_PHOTO
                else "architectural drawing"
            )
            prompt_parts.append(
                f"Edit mode: transform the provided {kind} into an illustrative "
                f"architectural concept variant for: {request.subject.strip()}. "
                "Preserve recognizable site structure; do not invent a different campus. "
                "Output must read as a presentation illustration, not a site survey photo."
            )
            avoid.append("photorealistic fake site evidence photo")
            avoid.append("claim the result is an as-built survey image")

        prompt_parts.append(
            "Keep forms plausible for the stated building type; prioritize clarity over spectacle."
        )
        if ctx.locale.lower().startswith("zh"):
            prompt_parts.append(
                "Composition should read clearly in a Chinese architectural presentation board."
            )

        prompt = " ".join(prompt_parts)
        prompt = re.sub(r"\s+", " ", prompt).strip()
        negative = "; ".join(avoid)
        prompt_hash = hashlib.sha256(
            f"{prompt}|{negative}|{request.width}x{request.height}|"
            f"{request.base_image_path or ''}|{request.mode.value}".encode()
        ).hexdigest()[:16]

        rationale = [
            f"image_type={request.image_type.value}",
            f"style={style_key}",
            f"mode={request.mode.value}",
            f"asset_policy={request.asset_policy.value}",
            f"context_phase={ctx.project_phase or 'n/a'}",
        ]
        if compose_mode:
            rationale.append("compose_mode=base_overlay")
        if edit_mode:
            rationale.append(f"edit_mode={request.mode.value}")

        return GenerationSpec(
            image_type=request.image_type,
            style=style_key,
            prompt=prompt,
            negative_prompt=negative,
            width=request.width,
            height=request.height,
            asset_policy=request.asset_policy,
            rationale=rationale,
            prompt_hash=prompt_hash,
            metadata={
                "project_type": ctx.project_type,
                "audience": ctx.audience,
                "page_archetype": ctx.page_archetype,
                "base_image_path": request.base_image_path,
                "overlay_cues": list(overlay_cues),
                "compose_mode": compose_mode,
                "edit_mode": edit_mode,
                "generation_mode": request.mode.value,
                "harmonize_output": request.harmonize_output,
                "type_label_zh": template.label_zh,
            },
        )
