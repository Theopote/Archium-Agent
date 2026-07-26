"""Topic 07 L1 — continue-work prefers unresolved design over presentation stage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from archium.application.product_continue_work import (
    design_loop_open,
    page_for_unresolved_design,
    resolve_continue_work_page_key,
)
from archium.domain.process import (
    DesignProcessFocus,
    ProcessPointer,
    ProjectProcessKind,
    ProjectProcessPhase,
)


def test_design_loop_open_for_comparing() -> None:
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
        label="比较 2 个概念方向",
    )
    assert design_loop_open(pointer) is True


def test_design_loop_closed_when_selected() -> None:
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.READY,
        focus=DesignProcessFocus.DIRECTION_SELECTED.value,
        label="方向已选定",
    )
    assert design_loop_open(pointer) is False


def test_page_for_unresolved_exploration(monkeypatch) -> None:
    exploration_id = uuid4()
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.EXPLORING.value,
        active_id=exploration_id,
        label="概念探索中",
    )

    class _Missions:
        def get_mission(self, _mid):
            return None

    monkeypatch.setattr(
        "archium.infrastructure.database.mission_repositories.MissionRepository",
        lambda _session: _Missions(),
    )
    assert page_for_unresolved_design(object(), pointer) == "concept-exploration"


def test_page_for_unresolved_mission_compare(monkeypatch) -> None:
    mission_id = uuid4()
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
        active_id=mission_id,
        label="Mission 下比较 2 个方向",
    )

    class _Mission:
        id = mission_id

    class _Missions:
        def get_mission(self, mid):
            return _Mission() if mid == mission_id else None

    monkeypatch.setattr(
        "archium.infrastructure.database.mission_repositories.MissionRepository",
        lambda _session: _Missions(),
    )
    assert page_for_unresolved_design(object(), pointer) == "project-mission"


def test_resolve_continue_prefers_design_over_outline(monkeypatch) -> None:
    project_id = uuid4()
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.ACTIVE,
        focus=DesignProcessFocus.COMPARING_DIRECTIONS.value,
        active_id=uuid4(),
        label="比较 3 个概念方向",
        updated_at=datetime.now(UTC),
    )

    monkeypatch.setattr(
        "archium.application.process.design_process_pointer.build_design_pointer",
        lambda _session, _pid: pointer,
    )
    monkeypatch.setattr(
        "archium.application.product_continue_work.page_for_active_design_orchestration",
        lambda _session, _pid: None,
    )
    monkeypatch.setattr(
        "archium.application.design_revise_persistence.load_pending_design_revise",
        lambda _session, _pid: None,
    )
    monkeypatch.setattr(
        "archium.infrastructure.database.mission_repositories.MissionRepository",
        lambda _session: type("M", (), {"get_mission": lambda self, _m: None})(),
    )

    page = resolve_continue_work_page_key(
        object(),
        project_id,
        presentation_stage_id="outline",
        slide_count=0,
    )
    assert page == "concept-exploration"


def test_resolve_continue_falls_back_to_presentation_when_design_ready(
    monkeypatch,
) -> None:
    project_id = uuid4()
    pointer = ProcessPointer(
        kind=ProjectProcessKind.DESIGN,
        phase=ProjectProcessPhase.READY,
        focus=DesignProcessFocus.COMMITTED.value,
        label="已提交 Mission",
    )
    monkeypatch.setattr(
        "archium.application.process.design_process_pointer.build_design_pointer",
        lambda _session, _pid: pointer,
    )
    monkeypatch.setattr(
        "archium.application.product_continue_work.page_for_active_design_orchestration",
        lambda _session, _pid: None,
    )
    monkeypatch.setattr(
        "archium.application.design_revise_persistence.load_pending_design_revise",
        lambda _session, _pid: None,
    )
    monkeypatch.setattr(
        "archium.application.context.workflow_navigation.workflow_entry_for_project",
        lambda _session, _pid: None,
    )
    page = resolve_continue_work_page_key(
        object(),
        project_id,
        presentation_stage_id="generate",
        slide_count=4,
    )
    assert page == "generate"
