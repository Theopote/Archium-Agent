"""Tests for design-iteration progress helpers."""

from __future__ import annotations

from archium.application.design_iteration_status import (
    format_vision_user_warning,
    summarize_design_iteration,
    visual_brief_status_label,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import ConceptDirectionStatus, ProjectOriginMode
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.domain.visual.vision_generation import ArchitectureImageType
from archium.domain.visual.visual_concept_brief import VisualConceptBrief
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
    VisualConceptBriefRepository,
)


def test_format_vision_user_warning_maps_settings() -> None:
    text = format_vision_user_warning(
        "未开启 vision_image_generation_enabled；仅保存文字视觉简报。"
    )
    assert "设置" in text
    assert "文字视觉简报已保存" in text


def test_visual_brief_status_label() -> None:
    assert visual_brief_status_label("imaged") == "已示意出图"
    assert visual_brief_status_label("ready") == "文字简报就绪"


def test_summarize_design_iteration_injectable(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="迭代进度", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
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
        VisualConceptBrief(
            project_id=project.id,
            mission_id=mission.id,
            concept_direction_id=direction.id,
            title="拱廊草图",
            composition_intent="低视角",
            subject="入口拱廊",
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            status="ready",
        )
    )
    db_session.commit()

    progress = summarize_design_iteration(db_session, mission.id)
    assert progress.direction_count == 1
    assert progress.selected_title == "窑洞再生"
    assert progress.injectable is True
    assert "可注入" in progress.summary_line()
    assert "文字简报就绪" in progress.summary_line()
