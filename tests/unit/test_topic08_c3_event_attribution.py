"""Topic 08 C3 — ProjectEvent member attribution (COLLAB-006)."""

from __future__ import annotations

from archium.application.project_access_service import ProjectAccessService
from archium.application.project_event_service import ProjectEventService
from archium.application.project_invite_service import ProjectInviteService
from archium.domain.access import LOCAL_ACTOR_ID, ProjectRole
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
from archium.domain.project import Project
from archium.domain.project_event import ProjectEventActor, ProjectEventType
from archium.infrastructure.database.repositories import ProjectRepository


def test_emit_stamps_member_actor_id(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="归因项目"),
        actor_id="architect-1",
    )
    events = ProjectEventService(db_session).list_for_project(project.id, limit=10)
    created = next(
        item for item in events if item.event_type == ProjectEventType.PROJECT_CREATED
    )
    assert created.member_actor_id == "architect-1"
    assert created.attribution_label() == "architect-1"
    assert created.actor == ProjectEventActor.USER


def test_intent_human_decision_projects_member_actor(db_session) -> None:
    evo = IntentEvolution().append(
        IntentEvolutionKind.DESIGN_DECISION,
        "选定生态共生",
        previous_summary="现代主义",
        new_summary="生态共生",
        reason="地域研究支持",
        actor_id="architect-2",
    )
    project = Project(name="决策归因", intent_evolution=evo)
    saved = ProjectRepository(db_session).create(project, actor_id=LOCAL_ACTOR_ID)
    db_session.flush()

    events = ProjectEventService(db_session).list_for_project(saved.id, limit=20)
    decision = next(
        item for item in events if item.event_type == ProjectEventType.DESIGN_DECISION
    )
    assert decision.member_actor_id == "architect-2"
    assert decision.actor == ProjectEventActor.USER


def test_invite_redeem_emits_member_joined(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="邀请归因"),
        actor_id=LOCAL_ACTOR_ID,
    )
    ProjectAccessService(db_session).ensure_default_owner(project.id)
    invite = ProjectInviteService(db_session).create_invite(
        project.id,
        ProjectRole.CLIENT,
        actor_id=LOCAL_ACTOR_ID,
        max_uses=2,
    )
    ProjectInviteService(db_session).redeem(
        invite.code,
        actor_id="client-join-1",
        display_name="甲方甲",
    )
    events = ProjectEventService(db_session).list_for_project(project.id, limit=20)
    joined = [
        item
        for item in events
        if item.source == "invite_redeem" and item.member_actor_id == "client-join-1"
    ]
    assert joined
    assert "甲方甲" in joined[0].summary or "client-join-1" in joined[0].summary
