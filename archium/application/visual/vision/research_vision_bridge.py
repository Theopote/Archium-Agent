"""Bridge DesignKnowledge / ArchitectureCase → Vision Engine seeds.

Visual seat service (no Agent). Produces illustrative ResearchVisionBundle only;
does not call image backends — callers may pass ImageRequest to VisionImageGenerationService.
"""

from __future__ import annotations

from uuid import UUID

from archium.domain.architecture_case import ArchitectureCase
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.research_vision import (
    ResearchVisionBundle,
    ResearchVisualKind,
    ResearchVisualReference,
)
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    VisionStylePreset,
)

_KIND_META: dict[ResearchVisualKind, tuple[str, ArchitectureImageType, VisionStylePreset, str, str]] = {
    # title_suffix, image_type, style, camera, style_label
    ResearchVisualKind.SPATIAL_ANALYSIS: (
        "空间分析图",
        ArchitectureImageType.SITE_DIAGRAM,
        VisionStylePreset.FLAT_ANALYTICAL_DIAGRAM,
        "architectural axonometric / flat analytical diagram",
        "flat analytical diagram",
    ),
    ResearchVisualKind.CONCEPT_SKETCH: (
        "概念草图",
        ArchitectureImageType.CONCEPT_SKETCH,
        VisionStylePreset.COMPETITION_CONCEPT_SKETCH,
        "architectural axonometric concept view",
        "competition concept sketch",
    ),
    ResearchVisualKind.MODERN_TRANSLATION: (
        "现代转译图",
        ArchitectureImageType.ATMOSPHERE_IMAGE,
        VisionStylePreset.SOFT_ATMOSPHERE,
        "eye-level soft atmosphere",
        "soft atmosphere",
    ),
}


class ResearchVisionBridgeService:
    """Map research insights to visual reference seeds for Vision Engine."""

    def bundle_from_design_knowledge(
        self,
        knowledge: DesignKnowledge,
        *,
        source_item_id: UUID | None = None,
        seed_source: str = "design_knowledge",
    ) -> ResearchVisionBundle | None:
        if knowledge is None or not knowledge.has_substance:
            return None
        topic = (knowledge.topic or "").strip() or "研究洞察"
        insight = (knowledge.insight or knowledge.principle or topic).strip()
        principle = (knowledge.principle or "").strip()
        spatial = (knowledge.spatial_translation or "").strip()
        material = (knowledge.material_strategy or "").strip()
        references = [
            self._build_reference(
                kind,
                topic=topic,
                insight=insight,
                principle=principle,
                spatial=spatial,
                material=material,
            )
            for kind in (
                ResearchVisualKind.SPATIAL_ANALYSIS,
                ResearchVisualKind.CONCEPT_SKETCH,
                ResearchVisualKind.MODERN_TRANSLATION,
            )
        ]
        return ResearchVisionBundle(
            topic=topic,
            insight=insight,
            principle=principle,
            spatial_translation=spatial,
            source_item_id=source_item_id,
            seed_source=seed_source,
            references=references,
        )

    def bundle_from_architecture_case(
        self,
        case: ArchitectureCase,
    ) -> ResearchVisionBundle | None:
        return self.bundle_from_design_knowledge(
            case.to_design_knowledge(),
            seed_source="architecture_case",
        )

    def bundles_from_items(
        self,
        items: list[ProjectKnowledgeItem],
        *,
        limit: int = 5,
    ) -> list[ResearchVisionBundle]:
        bundles: list[ResearchVisionBundle] = []
        for item in items:
            if len(bundles) >= max(1, limit):
                break
            dk = getattr(item, "design_knowledge", None)
            if dk is None or not isinstance(dk, DesignKnowledge):
                continue
            bundle = self.bundle_from_design_knowledge(
                dk,
                source_item_id=getattr(item, "id", None),
            )
            if bundle is not None and bundle.has_references:
                bundles.append(bundle)
        return bundles

    def preferred_prompt_for_direction(
        self,
        bundles: list[ResearchVisionBundle],
    ) -> ConceptVisualPrompt | None:
        for bundle in bundles:
            prompt = bundle.primary_visual_prompt()
            if prompt is not None and not prompt.is_empty():
                return prompt
        return None

    def _build_reference(
        self,
        kind: ResearchVisualKind,
        *,
        topic: str,
        insight: str,
        principle: str,
        spatial: str,
        material: str,
    ) -> ResearchVisualReference:
        title_suffix, image_type, style, camera, style_label = _KIND_META[kind]
        image_prompt = self._compose_image_prompt(
            kind,
            topic=topic,
            insight=insight,
            principle=principle,
            spatial=spatial,
            material=material,
        )
        elements = [
            f"research insight: {insight[:160]}",
        ]
        if principle:
            elements.append(f"design principle: {principle[:120]}")
        if spatial:
            elements.append(f"spatial translation: {spatial[:120]}")
        if material:
            elements.append(f"material strategy: {material[:100]}")
        elements.append(f"view kind: {kind.value}")
        return ResearchVisualReference(
            kind=kind,
            title=f"{topic} · {title_suffix}"[:200],
            insight=insight,
            visual_prompt=ConceptVisualPrompt(
                image_prompt=image_prompt[:500],
                camera=camera,
                style=style_label,
            ),
            image_type=image_type,
            style=style,
            purpose=f"{title_suffix}：{insight}"[:500],
            elements=elements[:12],
        )

    def _compose_image_prompt(
        self,
        kind: ResearchVisualKind,
        *,
        topic: str,
        insight: str,
        principle: str,
        spatial: str,
        material: str,
    ) -> str:
        core = spatial or principle or insight
        if kind == ResearchVisualKind.SPATIAL_ANALYSIS:
            return (
                f"architectural spatial analysis diagram of {topic}: "
                f"{core}. Clear figure-ground / courtyard or path logic, "
                f"annotated concept diagram, not photoreal."
            )[:500]
        if kind == ResearchVisualKind.MODERN_TRANSLATION:
            mat = f" Material attitude: {material}." if material else ""
            return (
                f"contemporary architectural atmosphere translating "
                f"{topic}: {insight}. Modern reading of "
                f"{principle or core}.{mat} Soft light, illustrative only."
            )[:500]
        # CONCEPT_SKETCH
        return (
            f"competition concept sketch for {topic}: {insight}. "
            f"Spatial idea: {core}. Architectural concept drawing, "
            f"not marketing render."
        )[:500]
