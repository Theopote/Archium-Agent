"""Unit tests for Research → Vision bridge."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.vision.research_vision_bridge import (
    ResearchVisionBridgeService,
)
from archium.domain.architecture_case import ArchitectureCase
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.research_vision import ResearchVisualKind
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    VisionAssetPolicy,
)


def _courtyard_knowledge() -> DesignKnowledge:
    return DesignKnowledge(
        topic="关中传统院落",
        insight="关中传统院落强调内向聚合",
        principle="以围合形成内向公共核",
        spatial_translation="四面围合、中心庭院、入口转折进入",
        material_strategy="土坯/砖木与灰瓦屋面",
        project_link="当代文化中心可转译为内向聚合庭院",
        evidence=["关中民居调研"],
    )


def test_design_knowledge_yields_three_visual_references() -> None:
    bundle = ResearchVisionBridgeService().bundle_from_design_knowledge(
        _courtyard_knowledge()
    )
    assert bundle is not None
    assert len(bundle.references) == 3
    kinds = {ref.kind for ref in bundle.references}
    assert kinds == {
        ResearchVisualKind.SPATIAL_ANALYSIS,
        ResearchVisualKind.CONCEPT_SKETCH,
        ResearchVisualKind.MODERN_TRANSLATION,
    }
    analysis = next(
        r for r in bundle.references if r.kind == ResearchVisualKind.SPATIAL_ANALYSIS
    )
    assert analysis.image_type == ArchitectureImageType.SITE_DIAGRAM
    assert "diagram" in analysis.visual_prompt.image_prompt.lower()
    assert "内向聚合" in bundle.insight

    sketch = next(
        r for r in bundle.references if r.kind == ResearchVisualKind.CONCEPT_SKETCH
    )
    req = sketch.to_image_request()
    assert req.asset_policy == VisionAssetPolicy.ILLUSTRATIVE_ONLY
    assert "内向聚合" in req.purpose or "内向聚合" in req.subject

    primary = bundle.primary_visual_prompt()
    assert primary is not None
    assert primary.image_prompt.strip()
    assert primary == sketch.visual_prompt


def test_empty_knowledge_skipped() -> None:
    assert ResearchVisionBridgeService().bundle_from_design_knowledge(
        DesignKnowledge()
    ) is None


def test_bundles_from_knowledge_items() -> None:
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="院落内向聚合",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        design_knowledge=_courtyard_knowledge(),
        category="research",
    )
    bundles = ResearchVisionBridgeService().bundles_from_items([item])
    assert len(bundles) == 1
    assert bundles[0].source_item_id == item.id
    prompt = ResearchVisionBridgeService().preferred_prompt_for_direction(bundles)
    assert prompt is not None
    assert "concept" in prompt.image_prompt.lower() or "sketch" in prompt.image_prompt.lower()


def test_architecture_case_maps_to_bundle() -> None:
    case = ArchitectureCase(
        id="test-courtyard",
        name="测试院落",
        design_problem="如何在高密度中保持内向静谧",
        strategy="围合院落",
        spatial_logic="中心庭院+环廊",
        transferable_principles=["内向聚合"],
        tags=["courtyard"],
    )
    bundle = ResearchVisionBridgeService().bundle_from_architecture_case(case)
    assert bundle is not None
    assert bundle.seed_source == "architecture_case"
    assert any(ref.kind == ResearchVisualKind.MODERN_TRANSLATION for ref in bundle.references)
    assert "【Research→Vision】" in bundle.to_prompt_block()
