"""Architectural style packs + type→default template (Vision Engine v0.2)."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    VisionStylePreset,
)


@dataclass(frozen=True)
class StylePresetDefinition:
    """One style pack expanded by Prompt Compiler."""

    key: str
    label_zh: str
    prose: str
    extra_avoid: tuple[str, ...] = ()
    best_for: tuple[ArchitectureImageType, ...] = ()


@dataclass(frozen=True)
class ImageTypeTemplate:
    """Default style / purpose / elements for a product image type."""

    image_type: ArchitectureImageType
    label_zh: str
    default_style: VisionStylePreset
    purpose: str
    default_elements: tuple[str, ...] = ()
    supports_base_overlay: bool = False


_STYLE_PACKS: tuple[StylePresetDefinition, ...] = (
    StylePresetDefinition(
        key=VisionStylePreset.COMPETITION_CONCEPT_SKETCH.value,
        label_zh="竞赛概念草图",
        prose=(
            "architectural competition concept sketch, restrained linework, "
            "professional presentation board quality"
        ),
        extra_avoid=("photoreal CGI hero shot",),
        best_for=(
            ArchitectureImageType.CONCEPT_SKETCH,
            ArchitectureImageType.PRESENTATION_ILLUSTRATION,
        ),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.MARKER_SKETCH.value,
        label_zh="马克笔",
        prose="architectural marker sketch on paper, confident strokes, warm gray markers",
        best_for=(ArchitectureImageType.SKETCH_NOTE, ArchitectureImageType.CONCEPT_SKETCH),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.PENCIL_SKETCH.value,
        label_zh="铅笔手绘",
        prose="architectural pencil sketch, graphite on white paper, soft shading",
        best_for=(ArchitectureImageType.SKETCH_NOTE, ArchitectureImageType.SECTION_ILLUSTRATION),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.AXONOMETRIC_DIAGRAM.value,
        label_zh="轴测分析图",
        prose=(
            "clear axonometric architectural diagram, flat colors, labeled circulation, "
            "legible arrows, minimal texture"
        ),
        best_for=(
            ArchitectureImageType.SITE_DIAGRAM,
            ArchitectureImageType.FLOW_DIAGRAM,
            ArchitectureImageType.SECTION_ILLUSTRATION,
        ),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM.value,
        label_zh="扁平分析图",
        prose=(
            "flat analytical architecture diagram, muted palette, bold arrows, "
            "simple massing blocks, presentation-ready"
        ),
        best_for=(
            ArchitectureImageType.SITE_DIAGRAM,
            ArchitectureImageType.FLOW_DIAGRAM,
            ArchitectureImageType.PRESENTATION_ILLUSTRATION,
        ),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.SOFT_ATMOSPHERE.value,
        label_zh="柔和氛围",
        prose=(
            "soft atmospheric architectural mood image, gentle daylight, calm landscape, "
            "not a glossy commercial render"
        ),
        best_for=(ArchitectureImageType.ATMOSPHERE_IMAGE,),
    ),
    StylePresetDefinition(
        key=VisionStylePreset.WATERCOLOR_NOTE.value,
        label_zh="水彩笔记",
        prose="architectural watercolor note sketch, light washes, hand-drawn feel",
        best_for=(ArchitectureImageType.MATERIAL_STUDY, ArchitectureImageType.SKETCH_NOTE),
    ),
)

_TYPE_TEMPLATES: dict[ArchitectureImageType, ImageTypeTemplate] = {
    ArchitectureImageType.CONCEPT_SKETCH: ImageTypeTemplate(
        image_type=ArchitectureImageType.CONCEPT_SKETCH,
        label_zh="概念草图",
        default_style=VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
        purpose="early design concept imagery for discussion",
        default_elements=("primary massing", "landscape cue", "human scale figure"),
    ),
    ArchitectureImageType.SITE_DIAGRAM: ImageTypeTemplate(
        image_type=ArchitectureImageType.SITE_DIAGRAM,
        label_zh="场地关系图",
        default_style=VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
        purpose="site relationship / massing diagram for explanation",
        default_elements=("site boundary", "access points", "key massing blocks"),
        supports_base_overlay=True,
    ),
    ArchitectureImageType.FLOW_DIAGRAM: ImageTypeTemplate(
        image_type=ArchitectureImageType.FLOW_DIAGRAM,
        label_zh="流线分析图",
        default_style=VisionStylePreset.AXONOMETRIC_DIAGRAM,
        purpose="circulation / flow analysis diagram",
        default_elements=("primary path", "secondary path", "bottleneck highlight"),
        supports_base_overlay=True,
    ),
    ArchitectureImageType.SECTION_ILLUSTRATION: ImageTypeTemplate(
        image_type=ArchitectureImageType.SECTION_ILLUSTRATION,
        label_zh="剖面示意",
        default_style=VisionStylePreset.AXONOMETRIC_DIAGRAM,
        purpose="sectional illustration of spatial strategy",
        default_elements=("ground line", "key volumes", "light / void cue"),
    ),
    ArchitectureImageType.ATMOSPHERE_IMAGE: ImageTypeTemplate(
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        label_zh="氛围图",
        default_style=VisionStylePreset.SOFT_ATMOSPHERE,
        purpose="mood / atmosphere background for presentation",
        default_elements=("soft daylight", "calm foreground"),
    ),
    ArchitectureImageType.MATERIAL_STUDY: ImageTypeTemplate(
        image_type=ArchitectureImageType.MATERIAL_STUDY,
        label_zh="材料研究",
        default_style=VisionStylePreset.WATERCOLOR_NOTE,
        purpose="material and tectonic study illustration",
        default_elements=("material swatch", "joint / detail cue"),
    ),
    ArchitectureImageType.PRESENTATION_ILLUSTRATION: ImageTypeTemplate(
        image_type=ArchitectureImageType.PRESENTATION_ILLUSTRATION,
        label_zh="页级插图",
        default_style=VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
        purpose="slide illustration supporting a verbal claim",
        default_elements=("clear focal subject",),
    ),
    ArchitectureImageType.SKETCH_NOTE: ImageTypeTemplate(
        image_type=ArchitectureImageType.SKETCH_NOTE,
        label_zh="手绘笔记",
        default_style=VisionStylePreset.MARKER_SKETCH,
        purpose="quick hand-drawn explanatory sketch note",
        default_elements=("annotation callout",),
    ),
}


class VisionStylePresetRegistry:
    """Lookup style packs and resolve type defaults (v0.2 barrier surface)."""

    def list_styles(self) -> tuple[StylePresetDefinition, ...]:
        return _STYLE_PACKS

    def get_style(self, key: str) -> StylePresetDefinition | None:
        normalized = key.strip()
        for pack in _STYLE_PACKS:
            if pack.key == normalized:
                return pack
        return None

    def style_prose(self, key: str) -> str:
        pack = self.get_style(key)
        if pack is not None:
            return pack.prose
        return key.replace("_", " ")

    def style_extra_avoid(self, key: str) -> tuple[str, ...]:
        pack = self.get_style(key)
        return pack.extra_avoid if pack is not None else ()

    def get_type_template(self, image_type: ArchitectureImageType) -> ImageTypeTemplate:
        return _TYPE_TEMPLATES[image_type]

    def list_type_templates(self) -> tuple[ImageTypeTemplate, ...]:
        return tuple(_TYPE_TEMPLATES[key] for key in ArchitectureImageType)

    def default_style_for(self, image_type: ArchitectureImageType) -> VisionStylePreset:
        return self.get_type_template(image_type).default_style

    def supports_base_overlay(self, image_type: ArchitectureImageType) -> bool:
        return self.get_type_template(image_type).supports_base_overlay


DEFAULT_STYLE_REGISTRY = VisionStylePresetRegistry()
