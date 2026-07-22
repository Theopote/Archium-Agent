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
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ImageNode,
    RenderScene,
    compute_scene_hash,
)
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


def _scene_for_slide(slide_id, *, x: float = 5.0) -> RenderScene:
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
                x=x,
                y=1,
                width=2,
                height=2,
                z_index=1,
                storage_uri="project://a.png",
                asset_path="project://a.png",
            )
        ],
    )


def _patch_ensure_scene(monkeypatch: pytest.MonkeyPatch, scene: RenderScene) -> None:
    def _fake_ensure(self, slide_id, **kwargs):  # noqa: ANN001
        return StudioSceneResult(
            scene=scene,
            scene_hash=compute_scene_hash(scene),
            preview_path=Path("unused.png"),
            reused=True,
        )

    monkeypatch.setattr(
        "archium.application.visual.studio_scene_service.StudioSceneService.ensure_scene_for_slide",
        _fake_ensure,
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
    assert comment.scene_revision_id is None
    assert comment.scene_hash == ""
    assert comment.node_snapshot_json == {}


def test_element_comment_repository_crud(db_session: Session) -> None:
    presentation, slide = _seed_slide(db_session)
    repo = ElementCommentRepository(db_session)
    revision_id = uuid4()
    comment = ElementComment(
        presentation_id=presentation.id,
        slide_id=slide.id,
        node_id="photo_right",
        layout_element_id="photo_right_el",
        note="放大一点",
        scene_revision_id=revision_id,
        scene_hash="abc123",
        node_snapshot_json={"id": "photo_right", "x": 5.0},
    )
    saved = repo.save(comment)
    loaded = repo.get(saved.id)
    assert loaded is not None
    assert loaded.node_id == "photo_right"
    assert loaded.status == ElementCommentStatus.PENDING
    assert loaded.scene_revision_id == revision_id
    assert loaded.scene_hash == "abc123"
    assert loaded.node_snapshot_json["id"] == "photo_right"

    listed = repo.list_by_slide(slide.id)
    assert len(listed) == 1
    assert listed[0].id == saved.id


def test_create_comment_rejects_missing_node(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id)
    _patch_ensure_scene(monkeypatch, scene)
    service = ElementCommentService(db_session, use_llm=False)
    with pytest.raises(WorkflowError, match="绑定节点不存在"):
        service.create_comment(
            slide_id=slide.id,
            node_id="missing",
            note="放大一点",
            presentation_id=presentation.id,
        )


def test_create_comment_binds_scene_version(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id)
    revision_id = uuid4()
    _patch_ensure_scene(monkeypatch, scene)
    monkeypatch.setattr(
        "archium.application.visual.scene_history_service.SceneHistoryService.latest_scene_revision_id",
        lambda self, s: revision_id,
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
    assert comment.scene_revision_id == revision_id
    assert comment.scene_hash == compute_scene_hash(scene)
    assert comment.node_snapshot_json.get("id") == "photo_right"
    assert comment.node_snapshot_json.get("x") == 5.0


def test_propose_marks_needs_rebase_when_revision_diverges(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id)
    v12 = uuid4()
    v14 = uuid4()
    _patch_ensure_scene(monkeypatch, scene)

    monkeypatch.setattr(
        "archium.application.visual.scene_history_service.SceneHistoryService.latest_scene_revision_id",
        lambda self, s: v14,
    )
    service = ElementCommentService(db_session, use_llm=False)
    repo = ElementCommentRepository(db_session)
    comment = repo.save(
        ElementComment(
            presentation_id=presentation.id,
            slide_id=slide.id,
            node_id="photo_right",
            note="放大一点",
            status=ElementCommentStatus.PENDING,
            scene_revision_id=v12,
            scene_hash=compute_scene_hash(scene),
            node_snapshot_json={"id": "photo_right", "x": 5.0},
        )
    )

    with pytest.raises(WorkflowError, match="needs_rebase"):
        service.propose_from_comment(comment.id)

    reloaded = repo.get(comment.id)
    assert reloaded is not None
    assert reloaded.status == ElementCommentStatus.NEEDS_REBASE
    assert reloaded.proposal_id is None


def test_propose_marks_needs_rebase_when_hash_diverges(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene_v12 = _scene_for_slide(slide.id, x=5.0)
    scene_v14 = _scene_for_slide(slide.id, x=6.5)
    revision_id = uuid4()
    _patch_ensure_scene(monkeypatch, scene_v14)
    monkeypatch.setattr(
        "archium.application.visual.scene_history_service.SceneHistoryService.latest_scene_revision_id",
        lambda self, s: revision_id,
    )
    service = ElementCommentService(db_session, use_llm=False)
    repo = ElementCommentRepository(db_session)
    comment = repo.save(
        ElementComment(
            presentation_id=presentation.id,
            slide_id=slide.id,
            node_id="photo_right",
            note="放大一点",
            status=ElementCommentStatus.PENDING,
            scene_revision_id=revision_id,
            scene_hash=compute_scene_hash(scene_v12),
            node_snapshot_json={"id": "photo_right", "x": 5.0},
        )
    )

    with pytest.raises(WorkflowError, match="needs_rebase"):
        service.propose_from_comment(comment.id)

    assert repo.get(comment.id).status == ElementCommentStatus.NEEDS_REBASE


def test_rebind_to_current_scene_clears_needs_rebase(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    presentation, slide = _seed_slide(db_session)
    scene = _scene_for_slide(slide.id, x=6.5)
    revision_id = uuid4()
    _patch_ensure_scene(monkeypatch, scene)
    monkeypatch.setattr(
        "archium.application.visual.scene_history_service.SceneHistoryService.latest_scene_revision_id",
        lambda self, s: revision_id,
    )
    service = ElementCommentService(db_session, use_llm=False)
    repo = ElementCommentRepository(db_session)
    comment = repo.save(
        ElementComment(
            presentation_id=presentation.id,
            slide_id=slide.id,
            node_id="photo_right",
            note="放大一点",
            status=ElementCommentStatus.NEEDS_REBASE,
            scene_revision_id=uuid4(),
            scene_hash="old-hash",
            node_snapshot_json={"id": "photo_right", "x": 5.0},
        )
    )

    rebound = service.rebind_to_current_scene(comment.id)
    assert rebound.status == ElementCommentStatus.PENDING
    assert rebound.scene_revision_id == revision_id
    assert rebound.scene_hash == compute_scene_hash(scene)
    assert rebound.node_snapshot_json.get("x") == 6.5


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
