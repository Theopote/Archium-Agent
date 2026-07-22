"""Tests for scene revision undo/redo used by Studio canvas edits."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_undo_service import SceneUndoService
from archium.application.visual.studio_scene_edit_service import StudioSceneEditService
from archium.domain.enums import ApprovalStatus, RevisionSource, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    LayoutPlanRepository,
    RenderSceneRepository,
)
from sqlalchemy.orm import Session


def _seed_slide_with_plan(db_session: Session) -> tuple[SlideSpec, LayoutPlan]:
    project = ProjectRepository(db_session).create(Project(name="Undo"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Deck",
            audience="甲方",
            purpose="测试",
            core_message="核心信息足够长。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="论点足够长。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="页面",
            message="本页核心结论：撤销应回退画布拖拽。",
            slide_type=SlideType.CONTENT,
        )
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    saved_plan = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved_plan.id
    presentations.save_slide(slide)
    scene = RenderScene(
        slide_id=slide.id,
        layout_plan_id=saved_plan.id,
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title_node",
                source_layout_element_id="title",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
                z_index=1,
                text="标题",
                font_family="Arial",
                font_size=18,
                color="#000000",
                line_height=1.2,
            ),
        ],
    )
    RenderSceneRepository(db_session).save(scene)
    SceneHistoryService(db_session).record_scene(
        slide=slide,
        scene=scene,
        change_source=RevisionSource.MANUAL_EDIT,
        scene_revision_source="manual",
        summary="初始 Scene",
    )
    db_session.commit()
    return slide, saved_plan


def test_scene_undo_reverts_canvas_move(db_session: Session) -> None:
    slide, plan = _seed_slide_with_plan(db_session)
    edit_service = StudioSceneEditService(db_session)
    edit_service.move_layout_element(slide.id, element_id="title", x=3.0, y=2.0)

    undo_service = SceneUndoService(db_session)
    assert undo_service.count_undo_steps(slide) == 1

    result, redo_revision_id = undo_service.undo(slide)
    assert redo_revision_id is not None
    assert "撤销" in result.summary.summary

    scene = RenderSceneRepository(db_session).get_by_layout_plan(plan.id)
    assert scene is not None
    node = scene.node_by_layout_element_id("title")
    assert node is not None
    assert node.x == 1.0
    assert node.y == 1.0

    updated_plan = LayoutPlanRepository(db_session).get(slide.layout_plan_id)  # type: ignore[arg-type]
    assert updated_plan is not None
    element = updated_plan.element_by_id("title")
    assert element is not None
    assert element.x == 1.0
    assert element.y == 1.0

    assert undo_service.count_undo_steps(slide) == 0

    redo_result = undo_service.redo(slide, redo_revision_id)
    assert "重做" in redo_result.summary.summary
    scene_after_redo = RenderSceneRepository(db_session).get_by_layout_plan(plan.id)
    assert scene_after_redo is not None
    moved = scene_after_redo.node_by_layout_element_id("title")
    assert moved is not None
    assert moved.x == 3.0
    assert moved.y == 2.0


def test_undo_then_new_edit_branches_from_live_parent(db_session: Session) -> None:
    """v10→move→v11→resize→v12→undo→v11→move→v13 parents v11; v12 kept."""
    slide, plan = _seed_slide_with_plan(db_session)
    history = SceneHistoryService(db_session)
    edit = StudioSceneEditService(db_session)
    undo = SceneUndoService(db_session)

    revisions = history.list_slide_scene_revisions(slide)
    v10 = revisions[0]

    edit.move_layout_element(slide.id, element_id="title", x=3.0, y=2.0)
    revisions = history.list_slide_scene_revisions(slide)
    v11 = revisions[0]
    assert str(v11.snapshot.get("parent_revision_id")) == str(v10.id)

    edit.resize_layout_element(
        slide.id,
        element_id="title",
        x=3.0,
        y=2.0,
        width=3.0,
        height=1.0,
    )
    revisions = history.list_slide_scene_revisions(slide)
    v12 = revisions[0]
    assert str(v12.snapshot.get("parent_revision_id")) == str(v11.id)

    _result, redo_v12 = undo.undo(slide)
    assert redo_v12 == v12.id
    live = RenderSceneRepository(db_session).get_by_layout_plan(plan.id)
    assert live is not None
    node = live.node_by_layout_element_id("title")
    assert node is not None
    assert node.x == pytest.approx(3.0)
    assert node.width == pytest.approx(2.0)
    assert undo.revision_id_for_live_scene(slide) == v11.id

    edit.move_layout_element(slide.id, element_id="title", x=4.5, y=2.5)
    revisions = history.list_slide_scene_revisions(slide)
    v13 = revisions[0]
    assert v13.id != v12.id
    assert str(v13.snapshot.get("parent_revision_id")) == str(v11.id)
    # Chronological prior sibling remains addressable.
    assert any(item.id == v12.id for item in revisions)

    # Undo from branched tip follows parent (v11), not chronological neighbor (v12).
    undo.undo(slide)
    assert undo.revision_id_for_live_scene(slide) == v11.id
    live_after = RenderSceneRepository(db_session).get_by_layout_plan(plan.id)
    assert live_after is not None
    restored = live_after.node_by_layout_element_id("title")
    assert restored is not None
    assert restored.x == pytest.approx(3.0)
    assert restored.y == pytest.approx(2.0)


def test_batch_move_creates_single_revision(db_session: Session) -> None:
    slide, _plan = _seed_slide_with_plan(db_session)
    history = SceneHistoryService(db_session)
    before = len(history.list_slide_scene_revisions(slide))
    StudioSceneEditService(db_session).move_layout_elements(
        slide.id,
        moves=[("title", 2.0, 2.0)],
    )
    after = history.list_slide_scene_revisions(slide)
    assert len(after) == before + 1
    assert after[0].snapshot.get("commands")
    assert after[0].snapshot["commands"][0]["command_type"] == "move_nodes"
