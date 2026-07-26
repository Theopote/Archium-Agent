"""Tests for applying Research→Vision seeds to concept directions."""

from __future__ import annotations

from archium.application.visual.vision.research_vision_apply import (
    apply_vision_bundles_to_directions,
)
from archium.application.visual.vision.research_vision_bridge import (
    ResearchVisionBridgeService,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.concept_visual_prompt import ConceptVisualPrompt
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import ConceptDirectionStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def test_apply_vision_seed_fills_empty_direction(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="视觉种子写入", project_type=ProjectType.CULTURE)
    )
    direction = ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            title="方向A",
            spatial_strategy="",
            status=ConceptDirectionStatus.DRAFT,
            sort_order=0,
        )
    )
    bundle = ResearchVisionBridgeService().bundle_from_design_knowledge(
        DesignKnowledge(
            topic="关中院落",
            insight="内向聚合",
            principle="围合公共核",
            spatial_translation="四面围合中心庭院",
        )
    )
    assert bundle is not None
    updated = apply_vision_bundles_to_directions(
        db_session,
        project.id,
        [bundle],
        only_if_empty=True,
    )
    assert len(updated) == 1
    assert updated[0].id == direction.id
    assert updated[0].visual_prompt is not None
    assert not updated[0].visual_prompt.is_empty()
    assert "庭院" in updated[0].spatial_strategy or "围合" in updated[0].spatial_strategy

    # Second apply should skip when only_if_empty
    again = apply_vision_bundles_to_directions(
        db_session,
        project.id,
        [bundle],
        only_if_empty=True,
    )
    assert again == []


def test_apply_skips_when_seed_already_present(db_session: Session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="已有种子", project_type=ProjectType.CULTURE)
    )
    ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            title="方向B",
            visual_prompt=ConceptVisualPrompt(
                image_prompt="existing sketch",
                camera="axonometric",
                style="concept sketch",
            ),
            status=ConceptDirectionStatus.DRAFT,
            sort_order=0,
        )
    )
    bundle = ResearchVisionBridgeService().bundle_from_design_knowledge(
        DesignKnowledge(topic="t", insight="i", principle="p", spatial_translation="s")
    )
    assert bundle is not None
    assert (
        apply_vision_bundles_to_directions(db_session, project.id, [bundle], only_if_empty=True)
        == []
    )
