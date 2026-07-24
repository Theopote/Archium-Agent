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
        direction: object | None = None,
    ) -> GenerationSpec:
        ctx = context or VisionGenerationContext()
        working = request
        seed_prompt = ""
        if direction is not None:
            from archium.application.visual.vision.concept_direction_visual_seed import (
                apply_direction_seed_to_request,
            )
            from archium.domain.concept_direction import ConceptDirection

            if isinstance(direction, ConceptDirection):
                working = apply_direction_seed_to_request(request, direction)
                vp = direction.visual_prompt
                if vp is not None:
                    seed_prompt = vp.image_prompt.strip()

        template = self._registry.get_type_template(working.image_type)

        if working.style is None or (
            isinstance(working.style, str) and not str(working.style).strip()
        ):
            style_key = template.default_style.value
        elif isinstance(working.style, VisionStylePreset):
            style_key = working.style.value
        else:
            style_key = str(working.style).strip()

        style_prose = self._registry.style_prose(style_key)
        purpose = (working.purpose or "").strip() or template.purpose

        elements = [item.strip() for item in working.elements if item.strip()]
        for default in template.default_elements:
            if default not in elements and len(elements) < 8:
                elements.append(default)
        if ctx.page_title and ctx.page_title not in elements:
            elements.append(f"page theme: {ctx.page_title}")
        if ctx.page_message and len(elements) < 8:
            elements.append(f"message cue: {ctx.page_message[:120]}")

        overlay_cues = [cue.strip() for cue in working.overlay_cues if cue.strip()]
        for cue in overlay_cues:
            if cue not in elements and len(elements) < 10:
                elements.append(f"overlay: {cue}")

        avoid = list(
            dict.fromkeys(
                [
                    *working.avoid,
                    *_DEFAULT_AVOID,
                    *self._registry.style_extra_avoid(style_key),
                ]
            )
        )
        if working.asset_policy in {
            VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            VisionAssetPolicy.FORBIDDEN_FOR_EVIDENCE,
        }:
            avoid.append("do not resemble an unverified site photograph used as project evidence")

        prompt_parts = [
            "Architectural visualization for a professional design presentation.",
            f"Image category: {working.image_type.value.replace('_', ' ')}.",
            f"Purpose: {purpose}.",
            f"Subject: {working.subject.strip()}.",
            f"Style: {style_prose}.",
        ]
        if seed_prompt:
            prompt_parts.insert(4, f"Primary scene seed: {seed_prompt}.")
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
            working.mode == VisionGenerationMode.TEXT_TO_IMAGE
            and bool(working.base_image_path)
            and self._registry.supports_base_overlay(working.image_type)
        )
        edit_mode = working.mode in {
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
                if working.mode == VisionGenerationMode.EDIT_FROM_PHOTO
                else "architectural drawing"
            )
            prompt_parts.append(
                f"Edit mode: transform the provided {kind} into an illustrative "
                f"architectural concept variant for: {working.subject.strip()}. "
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
            f"{prompt}|{negative}|{working.width}x{working.height}|"
            f"{working.base_image_path or ''}|{working.mode.value}|{seed_prompt}".encode()
        ).hexdigest()[:16]

        rationale = [
            f"image_type={working.image_type.value}",
            f"style={style_key}",
            f"mode={working.mode.value}",
            f"asset_policy={working.asset_policy.value}",
            f"context_phase={ctx.project_phase or 'n/a'}",
        ]
        if seed_prompt:
            rationale.append("direction_seed=concept_direction.visual_prompt")
        if compose_mode:
            rationale.append("compose_mode=base_overlay")
        if edit_mode:
            rationale.append(f"edit_mode={working.mode.value}")

        return GenerationSpec(
            image_type=working.image_type,
            style=style_key,
            prompt=prompt,
            negative_prompt=negative,
            width=working.width,
            height=working.height,
            asset_policy=working.asset_policy,
            rationale=rationale,
            prompt_hash=prompt_hash,
            metadata={
                "project_type": ctx.project_type,
                "audience": ctx.audience,
                "page_archetype": ctx.page_archetype,
                "base_image_path": working.base_image_path,
                "overlay_cues": list(overlay_cues),
                "compose_mode": compose_mode,
                "edit_mode": edit_mode,
                "generation_mode": working.mode.value,
                "harmonize_output": working.harmonize_output,
                "denoising_strength": working.denoising_strength,
                "type_label_zh": template.label_zh,
                "direction_seed": bool(seed_prompt),
            },
        )
