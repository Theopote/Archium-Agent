"""Tests for SceneRevisionTimelineService — list, restore, compare."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from archium.application.scene_revision_timeline_service import SceneRevisionTimelineService
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.domain.enums import ApprovalStatus, RevisionSource, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import RenderSceneRepository


def _seed_slide(db_session: Session) -> SlideSpec:
    project = ProjectRepository(db_session).create(Project(name="Timeline"))
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
    return presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="页面",
            message="本页核心结论：版本时间线恢复不得覆盖历史。",
            key_points=["一点", "二点", "三点"],
            slide_type=SlideType.CONTENT,
        )
    )


def _scene(*, slide_id, layout_plan_id, text: str, scene_id=None) -> RenderScene:
    return RenderScene(
        id=scene_id or uuid4(),
        slide_id=slide_id,
        layout_plan_id=layout_plan_id,
        page_width=1920,
        page_height=1080,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="t1",
                x=100,
                y=100,
                width=400,
                height=80,
                z_index=1,
                text=text,
                font_family="Arial",
                font_size=24,
                color="#000",
                line_height=1.2,
            )
        ],
    )


def test_restore_creates_new_revision_without_deleting_history(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    layout_plan_id = uuid4()
    history = SceneHistoryService(db_session)
    scenes = RenderSceneRepository(db_session)

    v1_scene = scenes.save(
        _scene(slide_id=slide.id, layout_plan_id=layout_plan_id, text="版本一")
    )
    v1_rev, _ = history.record_scene(
        slide=slide,
        scene=v1_scene,
        change_source=RevisionSource.MANUAL_EDIT,
        scene_revision_source="manual",
        summary="用户编辑：建立初版",
        qa_status="passed",
    )

    v2_scene = scenes.save(
        _scene(
            slide_id=slide.id,
            layout_plan_id=layout_plan_id,
            text="版本二",
            scene_id=v1_scene.id,
        ).model_copy(update={"version": v1_scene.version + 1})
    )
    v2_rev, _ = history.record_scene(
        slide=slide,
        scene=v2_scene,
        change_source=RevisionSource.AI_PROPOSAL,
        scene_revision_source="ai_proposal",
        parent_revision_id=v1_rev.id,
        summary="AI 提案：放大总平面图",
        qa_status="passed",
    )

    v3_scene = scenes.save(
        _scene(
            slide_id=slide.id,
            layout_plan_id=layout_plan_id,
            text="版本三",
            scene_id=v1_scene.id,
        ).model_copy(update={"version": v2_scene.version + 1})
    )
    history.record_scene(
        slide=slide,
        scene=v3_scene,
        change_source=RevisionSource.AUTO_REPAIR,
        scene_revision_source="automatic_repair",
        parent_revision_id=v2_rev.id,
        summary="QA 修复：图注越界",
        qa_status="repaired",
    )
    db_session.commit()

    before = SceneHistoryService(db_session).list_slide_scene_revisions(slide)
    assert len(before) == 3

    service = SceneRevisionTimelineService(db_session)
    result = service.restore_revision(slide=slide, source_revision_id=v1_rev.id)
    db_session.commit()

    after = SceneHistoryService(db_session).list_slide_scene_revisions(slide)
    assert len(after) == 4
    assert result.source_revision_id == v1_rev.id
    assert result.source_version == v1_rev.revision_number
    assert result.summary.version > v1_rev.revision_number
    assert result.summary.parent_revision_id == v1_rev.id

    # Historical revisions remain addressable.
    restored_ids = {revision.id for revision in after}
    assert v1_rev.id in restored_ids
    assert v2_rev.id in restored_ids
    scene = service.scene_for_revision(result.summary.revision_id)
    assert scene is not None
    assert any(
        isinstance(node, TextNode) and node.text == "版本一" for node in scene.nodes
    )


def test_list_summaries_marks_current_and_sources(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    layout_plan_id = uuid4()
    history = SceneHistoryService(db_session)
    scenes = RenderSceneRepository(db_session)

    scene = scenes.save(
        _scene(slide_id=slide.id, layout_plan_id=layout_plan_id, text="当前页")
    )
    history.record_scene(
        slide=slide,
        scene=scene,
        change_source=RevisionSource.MANUAL_EDIT,
        scene_revision_source="manual",
        summary="用户编辑：修改中心结论",
    )
    history.record_scene(
        slide=slide,
        scene=scene,
        change_source=RevisionSource.AI_PROPOSAL,
        scene_revision_source="ai_proposal",
        summary="AI 提案：调整构图",
    )
    db_session.commit()

    summaries = SceneRevisionTimelineService(db_session).list_summaries(slide)
    assert len(summaries) == 2
    assert any(item.source == "manual_edit" for item in summaries)
    assert any(item.source == "ai_proposal" for item in summaries)
    assert sum(1 for item in summaries if item.is_current) == 1
    current = next(item for item in summaries if item.is_current)
    assert current.accepted is True


def test_compare_revisions_returns_both_scenes(db_session: Session) -> None:
    slide = _seed_slide(db_session)
    layout_plan_id = uuid4()
    history = SceneHistoryService(db_session)
    scenes = RenderSceneRepository(db_session)

    left_scene = scenes.save(
        _scene(slide_id=slide.id, layout_plan_id=layout_plan_id, text="左侧")
    )
    left_rev, _ = history.record_scene(
        slide=slide,
        scene=left_scene,
        change_source=RevisionSource.MANUAL_EDIT,
        scene_revision_source="manual",
    )
    right_scene = scenes.save(
        _scene(
            slide_id=slide.id,
            layout_plan_id=layout_plan_id,
            text="右侧",
            scene_id=left_scene.id,
        ).model_copy(update={"version": left_scene.version + 1})
    )
    right_rev, _ = history.record_scene(
        slide=slide,
        scene=right_scene,
        change_source=RevisionSource.MANUAL_EDIT,
        scene_revision_source="manual",
    )
    db_session.commit()

    left, right = SceneRevisionTimelineService(db_session).compare_revisions(
        left_rev.id,
        right_rev.id,
    )
    assert any(isinstance(n, TextNode) and n.text == "左侧" for n in left.nodes)
    assert any(isinstance(n, TextNode) and n.text == "右侧" for n in right.nodes)
