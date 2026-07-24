"""Tests for VisualConceptBrief → VisualIntent / ImageRequest wiring."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.visual.vision import (
    apply_visual_concept_brief_to_intent,
    image_request_from_visual_concept_brief,
    visual_concept_brief_applies,
)
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.visual.enums import ContinuityRole, DensityLevel, VisualContentType
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionStylePreset,
)
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.domain.visual.visual_grammar import PageArchetype
from archium.domain.visual.visual_intent import VisualIntent


def _brief(**kwargs) -> VisualConceptBrief:
    defaults = {
        "project_id": uuid4(),
        "mission_id": uuid4(),
        "concept_direction_id": uuid4(),
        "title": "窑洞拱廊草图",
        "composition_intent": "低视角看向连续拱廊",
        "atmosphere": "黄土色温与柔和侧光",
        "image_type": ArchitectureImageType.CONCEPT_SKETCH,
        "style_preset": VisionStylePreset.MARKER_SKETCH,
        "subject": "窑洞再生入口拱廊",
        "elements": ["连续拱券", "半地下坡道"],
        "avoid": ["豪华地产效果图"],
        "status": "ready",
    }
    defaults.update(kwargs)
    return VisualConceptBrief(**defaults)


def _intent(**kwargs) -> VisualIntent:
    defaults = {
        "slide_id": uuid4(),
        "presentation_id": uuid4(),
        "communication_goal": "传达概念方向",
        "audience_takeaway": "窑洞再生可讨论",
        "visual_priority": "主图示意",
        "dominant_content_type": VisualContentType.HERO_IMAGE,
        "density_level": DensityLevel.BALANCED,
        "continuity_role": ContinuityRole.OPENING,
        "approval_status": ApprovalStatus.PENDING,
    }
    defaults.update(kwargs)
    return VisualIntent(**defaults)


def test_image_request_from_visual_concept_brief() -> None:
    request = image_request_from_visual_concept_brief(_brief())
    assert request.image_type == ArchitectureImageType.CONCEPT_SKETCH
    assert request.style == VisionStylePreset.MARKER_SKETCH
    assert "拱廊" in request.subject
    assert "连续拱券" in request.elements
    assert request.asset_policy.value == "illustrative_only"


def test_visual_concept_brief_applies_skips_diagnosis() -> None:
    assert visual_concept_brief_applies(page_archetype=PageArchetype.NARRATIVE_OPENING)
    assert visual_concept_brief_applies(page_archetype=PageArchetype.DESIGN_STRATEGY)
    assert not visual_concept_brief_applies(
        page_archetype=PageArchetype.SITE_PROBLEM_DIAGNOSIS
    )


def test_apply_visual_concept_brief_seeds_image_request_and_hero() -> None:
    asset_id = uuid4()
    brief = _brief(asset_id=asset_id, status="imaged")
    intent = apply_visual_concept_brief_to_intent(_intent(), brief)

    assert intent.image_request is not None
    assert intent.image_request.subject == "窑洞再生入口拱廊"
    assert intent.hero_asset_id == asset_id
    assert "黄土" in intent.emotional_tone
    assert "低视角" in intent.composition_strategy


def test_apply_does_not_override_existing_image_request_or_hero() -> None:
    existing = ImageRequest(
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        subject="already set",
    )
    hero = uuid4()
    intent = apply_visual_concept_brief_to_intent(
        _intent(
            image_request=existing,
            hero_asset_id=hero,
            emotional_tone="已有语气",
            composition_strategy="已有构图",
        ),
        _brief(asset_id=uuid4()),
    )
    assert intent.image_request is existing
    assert intent.hero_asset_id == hero
    assert intent.emotional_tone == "已有语气"


def test_generate_for_slide_prefers_visual_concept_brief(db_session) -> None:
    from archium.application.visual.visual_intent_service import VisualIntentService
    from archium.domain.concept_direction import ConceptDirection
    from archium.domain.enums import ConceptDirectionStatus, ProjectOriginMode
    from archium.domain.presentation import Presentation
    from archium.domain.project import Project
    from archium.domain.project_mission import ProjectMission
    from archium.domain.slide import SlideSpec
    from archium.infrastructure.database.mission_repositories import MissionRepository
    from archium.infrastructure.database.repositories import (
        ConceptDirectionRepository,
        PresentationRepository,
        ProjectRepository,
        VisualConceptBriefRepository,
    )
    from archium.infrastructure.database.visual_repositories import VisualIntentRepository

    project = ProjectRepository(db_session).create(
        Project(name="概念视觉", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="文化中心",
            task_statement="探索概念",
        )
    )
    direction = ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            mission_id=mission.id,
            title="窑洞再生",
            summary="窑洞原型",
            status=ConceptDirectionStatus.SELECTED,
        )
    )
    VisualConceptBriefRepository(db_session).create(
        _brief(
            project_id=project.id,
            mission_id=mission.id,
            concept_direction_id=direction.id,
            subject="窑洞再生入口拱廊",
        )
    )
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="概念汇报")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch-1",
            order=0,
            slide_type=SlideType.TITLE,
            title="概念缘起",
            message="窑洞再生的空间体验",
        )
    )
    db_session.commit()

    intents = VisualIntentRepository(db_session)
    intents.save = MagicMock(side_effect=lambda intent: intent)  # type: ignore[method-assign]
    service = VisualIntentService(db_session, llm=None)
    service._intents = intents  # noqa: SLF001

    intent = service.generate_for_slide(slide, use_llm=False)

    assert intent.image_request is not None
    assert intent.image_request.subject == "窑洞再生入口拱廊"
    assert intent.image_request.image_type == ArchitectureImageType.CONCEPT_SKETCH
