"""Unit tests for FactLedgerService."""

from __future__ import annotations

from archium.application.fact_ledger_service import FactLedgerService
from archium.application.fact_validation_service import FactValidationService
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from sqlalchemy.orm import Session


def _seed_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="Fact Ledger 测试"))


def test_ledger_lists_standard_keys_and_missing(db_session: Session) -> None:
    project = _seed_project(db_session)
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="bed_count",
            label="床位数",
            value="800",
            unit="床",
        )
    )

    ledger = FactLedgerService(db_session).get_ledger(project.id)

    assert ledger.confirmed_count == 0
    assert ledger.pending_count == 1
    assert "bed_count" not in ledger.missing_standard_keys
    assert "project_name" in ledger.missing_standard_keys


def test_confirm_fact_clears_conflict_group(db_session: Session) -> None:
    project = _seed_project(db_session)
    fact = FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12.5",
            unit="公顷",
            conflict_group="key:site_area",
        )
    )
    fact.mark_conflicted()
    FactRepository(db_session).update(fact)

    confirmed = FactLedgerService(db_session).confirm_fact(fact.id)

    assert confirmed.is_confirmed
    assert confirmed.conflict_group is None
    refreshed = ProjectRepository(db_session).get_by_id(project.id)
    assert refreshed is not None
    assert any(
        e.kind.value == "evidence" and "用地面积" in e.summary
        for e in refreshed.intent_evolution.events
    )


def test_confirm_fact_writes_document_evidence_to_mission(db_session: Session) -> None:
    from archium.domain.intent.design_intent import DesignIntent
    from archium.domain.intent.intent_evidence import IntentEvidenceSourceType
    from archium.domain.project_mission import ProjectMission
    from archium.infrastructure.database.mission_repositories import MissionRepository

    project = _seed_project(db_session)
    MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="任务",
            task_statement="改造医院",
            design_intent=DesignIntent(theme="既有更新"),
        )
    )
    fact = FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="location",
            label="地点",
            value="西安",
            verification_status=VerificationStatus.EXTRACTED,
        )
    )
    FactLedgerService(db_session).confirm_fact(fact.id)
    mission = MissionRepository(db_session).list_missions_by_project(project.id)[0]
    assert mission.design_intent is not None
    assert mission.design_intent.evidence
    assert (
        mission.design_intent.evidence[0].source_type == IntentEvidenceSourceType.DOCUMENT
    )
    assert "西安" in mission.design_intent.evidence[0].statement


def test_distinct_area_metrics_do_not_conflict(db_session: Session) -> None:
    project = _seed_project(db_session)
    repo = FactRepository(db_session)
    repo.create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12.5",
            unit="公顷",
        )
    )
    repo.create(
        ProjectFact(
            project_id=project.id,
            key="building_area",
            label="建筑面积",
            value="85000",
            unit="平方米",
        )
    )

    result = FactValidationService(db_session).validate(project.id)

    assert not any("冲突组" in issue for issue in result.issues)
    assert all(
        fact.verification_status != VerificationStatus.CONFLICTED for fact in result.facts
    )
    ledger = FactLedgerService(db_session).get_ledger(project.id)
    assert ledger.conflict_count == 0


def test_semantic_alias_conflict_detection(db_session: Session) -> None:
    project = _seed_project(db_session)
    repo = FactRepository(db_session)
    repo.create(
        ProjectFact(
            project_id=project.id,
            key="plot_ratio",
            label="容积率",
            value="2.5",
        )
    )
    repo.create(
        ProjectFact(
            project_id=project.id,
            key="far",
            label="FAR",
            value="3.0",
        )
    )

    result = FactValidationService(db_session).validate(project.id)

    assert any("语义冲突" in issue for issue in result.issues)
    conflicted = [fact for fact in result.facts if fact.verification_status == VerificationStatus.CONFLICTED]
    assert len(conflicted) == 2
    assert all(fact.conflict_group == "alias:plot_ratio" for fact in conflicted)


def test_update_fact_persists_value(db_session: Session) -> None:
    project = _seed_project(db_session)
    fact = FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="floors",
            label="层数",
            value="12",
        )
    )

    updated = FactLedgerService(db_session).update_fact(fact.id, value="15", unit="层")

    assert str(updated.value) == "15"
    assert updated.unit == "层"
