"""Topic 08 C3 — role-aware navigation (COLLAB-005)."""

from __future__ import annotations

from archium.application.product_continue_work import resolve_continue_work_page_key
from archium.application.project_access_service import ProjectAccessService
from archium.application.role_navigation import resolve_role_navigation, role_label
from archium.domain.access import LOCAL_ACTOR_ID, ProjectRole
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository


def test_client_primary_page_is_deliver_when_slides(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="甲方项目"))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "client-1",
        ProjectRole.CLIENT,
        display_name="甲方",
        actor=LOCAL_ACTOR_ID,
    )
    hint = resolve_role_navigation(
        db_session,
        project.id,
        actor_id="client-1",
        slide_count=12,
        presentation_stage_id="outline",
    )
    assert hint.role == ProjectRole.CLIENT
    assert hint.primary_page_key == "deliver"
    assert hint.can_edit is False
    assert hint.is_read_leaning is True
    assert "甲方" in role_label(hint.role)


def test_continue_work_routes_client_to_deliver(db_session, monkeypatch) -> None:
    project = ProjectRepository(db_session).create(Project(name="甲方继续"))
    access = ProjectAccessService(db_session)
    access.add_member(
        project.id,
        "client-2",
        ProjectRole.CLIENT,
        actor=LOCAL_ACTOR_ID,
    )
    monkeypatch.setattr(
        "archium.application.design_revise_persistence.load_pending_design_revise",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "archium.application.process.design_process_pointer.build_design_pointer",
        lambda *_a, **_k: type(
            "P",
            (),
            {
                "design_focus": lambda self: None,
                "focus": "idle",
                "label": "",
            },
        )(),
    )
    page = resolve_continue_work_page_key(
        db_session,
        project.id,
        presentation_stage_id="outline",
        slide_count=8,
        actor_id="client-2",
    )
    assert page == "deliver"


def test_architect_keeps_design_loop_when_comparing(db_session, monkeypatch) -> None:
    from archium.domain.process import (
        DesignProcessFocus,
        ProcessPointer,
        ProjectProcessKind,
        ProjectProcessPhase,
    )

    project = ProjectRepository(db_session).create(Project(name="建筑师继续"))
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
        label="比较 2 个概念方向",
    )
    monkeypatch.setattr(
        "archium.application.design_revise_persistence.load_pending_design_revise",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "archium.application.process.design_process_pointer.build_design_pointer",
        lambda *_a, **_k: pointer,
    )
    monkeypatch.setattr(
        "archium.infrastructure.database.mission_repositories.MissionRepository",
        lambda _session: type("M", (), {"get_mission": lambda self, _m: None})(),
    )
    page = resolve_continue_work_page_key(
        db_session,
        project.id,
        presentation_stage_id="outline",
        slide_count=0,
        actor_id=LOCAL_ACTOR_ID,
    )
    assert page == "concept-exploration"
