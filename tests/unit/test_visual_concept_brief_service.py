"""Unit tests for Vision Engine visual concept brief service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.concept_direction_service import ConceptDirectionService
from archium.application.visual.vision import VisualConceptBriefService
from archium.config.settings import Settings
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import (
    ConceptDirectionStatus,
    ProjectOriginMode,
    TaskNature,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    GenerationSpec,
    VisionAssetPolicy,
    VisionGenerationResult,
    VisionStylePreset,
)
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
)
from archium.infrastructure.llm.visual_concept_brief_schemas import VisualConceptBriefDraft


@pytest.fixture
def concept_mission(db_session):
    project = ProjectRepository(db_session).create(
        Project(
            name="黄土高原文化中心",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="文化中心概念探索",
            task_statement="探索嵌入地域文化的小型文化中心概念方向",
            task_natures=[TaskNature.PLANNING, TaskNature.RESEARCH],
            design_intent=DesignIntent(
                theme="地域文化再生",
                problem_statement="如何在缺少任务书时建立可讨论方向？",
                desired_experience="在地认同与开放交流",
            ),
            project_context="仅有一句话想法",
        )
    )
    db_session.commit()
    return mission


@pytest.fixture
def draft_direction(db_session, concept_mission):
    llm = MagicMock()
    llm.generate_structured.return_value = ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(
                title="窑洞再生",
                summary="以窑洞原型转译当代公共空间",
                theme="窑洞当代化",
                spatial_idea="半地下连续拱廊",
                experience_focus="庇护与仪式感",
                differentiator="窑洞构造作为主叙事",
            ),
            ConceptDirectionDraft(
                title="台地聚落",
                summary="沿台地展开的开放群落",
                theme="台地生活",
                spatial_idea="分散院落",
                experience_focus="日常穿行",
                differentiator="以台地组织公共空间",
            ),
        ]
    )
    generated = ConceptDirectionService(db_session, llm).generate_directions(
        concept_mission.id, count=2
    )
    assert generated.directions[0].status == ConceptDirectionStatus.DRAFT
    return generated.directions[0]


@pytest.fixture
def seeded_direction(db_session, concept_mission):
    direction = ConceptDirection(
        project_id=concept_mission.project_id,
        mission_id=concept_mission.id,
        title="窑洞再生",
        summary="以窑洞原型转译当代公共空间",
        theme="窑洞当代化",
        spatial_idea="半地下连续拱廊",
        spatial_strategy="半地下拱廊轴线",
        formal_language="厚重土墙与连续拱券",
        material_strategy="夯土与石基",
        reference_dna=["黄土高原窑洞类型"],
        visual_prompt=ConceptVisualPrompt(
            image_prompt="yaodong cultural center in loess plateau, continuous vaults",
            camera="architectural axonometric",
            style="concept sketch",
        ),
        experience_focus="庇护与仪式感",
        differentiator="窑洞构造作为主叙事",
        status=ConceptDirectionStatus.DRAFT,
    )
    created = ConceptDirectionRepository(db_session).create(direction)
    db_session.commit()
    return created


def test_synthesize_visual_brief_text_only(db_session, draft_direction) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = VisualConceptBriefDraft(
        title="窑洞拱廊草图",
        composition_intent="低视角看向连续拱廊深处",
        atmosphere="黄土色温与柔和侧光",
        diagram_intent="",
        image_type="concept_sketch",
        style_preset="marker_sketch",
        subject="窑洞再生文化中心入口拱廊",
        elements=["连续拱券", "半地下坡道", "柔和天光"],
        avoid=["豪华地产效果图", "玻璃幕墙塔楼"],
    )
    settings = Settings(vision_image_generation_enabled=False)
    service = VisualConceptBriefService(db_session, llm, settings=settings)

    result = service.synthesize_for_direction(draft_direction.id, generate_image=False)

    assert result.brief.status == "ready"
    assert result.brief.image_type == ArchitectureImageType.CONCEPT_SKETCH
    assert result.brief.style_preset == VisionStylePreset.MARKER_SKETCH
    assert "拱廊" in result.brief.compiled_prompt or result.brief.compiled_prompt
    assert result.image_attempted is False
    assert result.image_succeeded is False

    latest = service.get_latest_for_direction(draft_direction.id)
    assert latest is not None
    assert latest.id == result.brief.id


def test_synthesize_visual_brief_with_image_when_enabled(
    db_session, draft_direction
) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = VisualConceptBriefDraft(
        title="窑洞氛围示意",
        composition_intent="侧光穿过拱廊",
        atmosphere="温润黄土氛围",
        subject="窑洞再生氛围示意",
        image_type="atmosphere_image",
        style_preset="soft_atmosphere",
        elements=["拱廊", "尘光"],
        avoid=["现场照片证据感"],
    )
    image_service = MagicMock()
    image_service.generate.return_value = VisionGenerationResult(
        success=True,
        spec=GenerationSpec(
            image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
            style="soft_atmosphere",
            prompt="compiled atmosphere prompt",
            asset_policy=VisionAssetPolicy.ILLUSTRATIVE_ONLY,
            width=1280,
            height=720,
        ),
        storage_path="projects/demo/vision/atmosphere.png",
        asset_id=draft_direction.id,
    )
    settings = Settings(vision_image_generation_enabled=True)
    service = VisualConceptBriefService(
        db_session,
        llm,
        settings=settings,
        image_service=image_service,
    )

    result = service.synthesize_for_direction(draft_direction.id, generate_image=True)

    assert result.image_attempted is True
    assert result.image_succeeded is True
    assert result.brief.status == "imaged"
    assert result.brief.image_path == "projects/demo/vision/atmosphere.png"
    image_service.generate.assert_called_once()
    assert image_service.generate.call_args.kwargs.get("direction") is not None


def test_synthesize_skips_image_when_disabled(db_session, draft_direction) -> None:
    llm = MagicMock()
    llm.generate_structured.return_value = VisualConceptBriefDraft(
        title="仅文字",
        composition_intent="中景构图",
        subject="概念示意",
    )
    image_service = MagicMock()
    settings = Settings(vision_image_generation_enabled=False)
    service = VisualConceptBriefService(
        db_session,
        llm,
        settings=settings,
        image_service=image_service,
    )

    result = service.synthesize_for_direction(draft_direction.id, generate_image=True)

    assert result.brief.status == "ready"
    assert result.image_attempted is False
    assert any("vision_image_generation_enabled" in item for item in result.warnings)
    image_service.generate.assert_not_called()


def test_synthesize_uses_direction_seed_without_llm(db_session, seeded_direction) -> None:
    llm = MagicMock()
    settings = Settings(vision_image_generation_enabled=False)
    service = VisualConceptBriefService(db_session, llm, settings=settings)

    result = service.synthesize_for_direction(seeded_direction.id, generate_image=False)

    llm.generate_structured.assert_not_called()
    assert any("visual_prompt" in item for item in result.warnings)
    assert result.brief.extra_json.get("seed_source") == "concept_direction.visual_prompt"
    assert "Primary scene seed" in result.brief.compiled_prompt or "yaodong" in result.brief.compiled_prompt.lower()
    assert result.brief.extra_json.get("direction_seed") is True
