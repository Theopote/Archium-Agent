"""Tests for ElementComment domain, repository, and status sync."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.element_comment_service import ElementCommentService
from archium.application.visual.studio_scene_service import StudioSceneResult
from archium.domain.enums import SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.element_comment import ElementComment, ElementCommentStatus
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import ElementCommentRepository
from sqlalchemy.orm import Session


def _seed_slide(session: Session) -> tuple[Presentation, object]:
    project = ProjectRepository(session).create(Project(name="Element Comment Project"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Comment Deck")
    )
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            title="Page",
            slide_type=SlideType.CONTENT,
            order=0,
            chapter_id="ch1",
            message="元素评论测试页。",
        )
    )
    return presentation, slide


def _scene_for_slide(slide_id) -> RenderScene:
    return RenderScene(
        slide_id=slide_id,
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="photo_right",
                source_layout_element_id="photo_right_el",
                x=5,
                y=1,
                width=2,
                height=2,
                z_index=1,
                storage_uri="project://a.png",
                asset_path="project://a.png",
            )
        ],
    )


def test_element_comment_defaults() -> None:
    comment = ElementComment(
        presentation_id=uuid4(),
        slide_id=uuid4(),
        node_id="photo_right",
        note="放大一点",
    )
    assert comment.status == ElementCommentStatus.PENDING
    assert comment.created_by == "user"
    assert comment.proposal_id is None


def test_element_comment_repository_crud(db_session: Session) -> None:
    presentation, slide = _seed_slide(db_session)
    repo = ElementCommentRepository(db_session)
    comment = ElementComment(
        presentation_id=presentation.id,
        slide_id=slide.id,
        node_id="photo_right",
        layout_element_id="photo_right_el",
        note="放大一点",
    )
    saved = repo.save(comment)
    loaded = repo.get(saved.id)
    assert loaded is not None
    assert loaded.node_id == "photo_right"
    assert loaded.status == ElementCommentStatus.PENDING

    listed = repo.list_by_slide(slide.id)
    assert len(listed) == 1
    assert listed[0].id == saved.id


def test_create_comment_rejects_missing_node(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id)

    def _fake_ensure(self, slide_id, **kwargs):  # noqa: ANN001
        return StudioSceneResult(
            scene=scene,
            scene_hash="hash",
            preview_path=Path("unused.png"),
            reused=True,
        )

    monkeypatch.setattr(
        "archium.application.visual.studio_scene_service.StudioSceneService.ensure_scene_for_slide",
        _fake_ensure,
    )
    service = ElementCommentService(db_session, use_llm=False)
    with pytest.raises(WorkflowError, match="绑定节点不存在"):
        service.create_comment(
            slide_id=slide.id,
            node_id="missing",
            note="放大一点",
            presentation_id=presentation.id,
        )


def test_create_comment_pending(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id)

    def _fake_ensure(self, slide_id, **kwargs):  # noqa: ANN001
        return StudioSceneResult(
            scene=scene,
            scene_hash="hash",
            preview_path=Path("unused.png"),
            reused=True,
        )

    monkeypatch.setattr(
        "archium.application.visual.studio_scene_service.StudioSceneService.ensure_scene_for_slide",
        _fake_ensure,
    )
    service = ElementCommentService(db_session, use_llm=False)
    comment = service.create_comment(
        slide_id=slide.id,
        node_id="photo_right",
        note="放大一点",
        layout_element_id="photo_right_el",
        presentation_id=presentation.id,
    )
    assert comment.status == ElementCommentStatus.PENDING
    assert comment.node_id == "photo_right"


def test_sync_from_proposal_decision_accept_reject(db_session: Session) -> None:
    presentation, slide = _seed_slide(db_session)
    repo = ElementCommentRepository(db_session)
    proposal_id = uuid4()
    comment = repo.save(
        ElementComment(
            presentation_id=presentation.id,
            slide_id=slide.id,
            node_id="photo_right",
            note="放大一点",
            status=ElementCommentStatus.PROPOSED,
            proposal_id=proposal_id,
        )
    )
    service = ElementCommentService(db_session, use_llm=False)

    accepted_proposal = SceneChangeProposal(
        proposal_id=proposal_id,
        presentation_id=presentation.id,
        slide_id=slide.id,
        base_scene_hash="abc",
        base_scene=_scene_for_slide(slide.id),
        proposed_scene=_scene_for_slide(slide.id),
        status=ProposalStatus.ACCEPTED,
    )
    synced = service.sync_from_proposal_decision(accepted_proposal)
    assert len(synced) == 1
    assert synced[0].status == ElementCommentStatus.ACCEPTED

    repo.save(comment.model_copy(update={"status": ElementCommentStatus.PROPOSED}))
    rejected_proposal = accepted_proposal.model_copy(update={"status": ProposalStatus.REJECTED})
    synced_reject = service.sync_from_proposal_decision(rejected_proposal)
    assert synced_reject[0].status == ElementCommentStatus.REJECTED
