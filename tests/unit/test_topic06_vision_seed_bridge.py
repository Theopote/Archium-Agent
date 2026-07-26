"""Topic 06 P1 — ConceptVisualPrompt → ImageRequest seed bridge."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision.concept_direction_visual_seed import (
    image_request_from_concept_direction,
)
from archium.application.visual.vision.intent_suggester import suggest_image_request_for_slide
from archium.application.visual.vision.visual_concept_brief_intent import (
    image_request_from_visual_concept_brief,
)
from archium.domain.architectural_asset import (
    ArchitecturalAssetRole,
    architectural_asset_from_parts,
)
from archium.domain.asset import Asset
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.enums import AssetType, SlideType
from archium.domain.knowledge_reference import KnowledgeUsage
from archium.domain.slide import SlideSpec
from archium.domain.visual.vision_generation import VisionAssetPolicy
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual.visual_grammar import PageArchetype


def test_direction_image_request_has_seed_source_and_illustrative() -> None:
    direction = ConceptDirection(
        project_id=uuid4(),
        title="庭院文化核",
        summary="以内向院落组织公共空间",
        visual_prompt=ConceptVisualPrompt(
            image_prompt="marker sketch of courtyard cultural core",
            camera="axonometric",
            style="marker sketch",
        ),
        spatial_strategy="四面围合",
    )
    request = image_request_from_concept_direction(direction)
    assert request.seed_source == "concept_direction"
    assert request.asset_policy == VisionAssetPolicy.ILLUSTRATIVE_ONLY
    assert "courtyard" in request.subject.lower() or "marker" in request.subject.lower()


def test_brief_and_suggester_seed_sources() -> None:
    brief = VisualConceptBrief(
        project_id=uuid4(),
        concept_direction_id=uuid4(),
        title="概念视觉",
        subject="soft atmosphere plaza",
        image_type="atmosphere_image",
        style_preset="soft_atmosphere",
    )
    assert image_request_from_visual_concept_brief(brief).seed_source == "brief"

    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="设计策略",
        message="流线示意",
        slide_type=SlideType.CONTENT,
    )
    suggested = suggest_image_request_for_slide(
        slide, page_archetype=PageArchetype.DESIGN_STRATEGY
    )
    assert suggested is not None
    assert suggested.seed_source == "suggester"
    assert suggested.asset_policy == VisionAssetPolicy.ILLUSTRATIVE_ONLY


def test_generated_asset_stays_illustrative_via_facade() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="vision.png",
        path="/tmp/vision.png",
        asset_type=AssetType.IMAGE,
        tags=["ai_generated", "illustrative"],
        metadata={
            "origin": "ai_generated",
            "asset_policy": "illustrative_only",
            "seed_source": "concept_direction",
        },
    )
    facade = architectural_asset_from_parts(asset)
    assert facade.role == ArchitecturalAssetRole.REFERENCE
    assert facade.usage == KnowledgeUsage.ILLUSTRATIVE
