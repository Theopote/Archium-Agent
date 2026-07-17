"""Unit tests for FactValidationService."""

from __future__ import annotations

import pytest
from archium.application.fact_validation_service import FactValidationService
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="测试项目"))


def test_validate_flags_empty_value_as_conflict(db_session: Session, project: Project) -> None:
    fact_repo = FactRepository(db_session)
    fact_repo.create(
        ProjectFact(
            project_id=project.id,
            key="empty_metric",
            label="空指标",
            value="",
        )
    )

    result = FactValidationService(db_session).validate(project.id)

    assert len(result.issues) == 1
    assert "空指标" in result.issues[0]
    assert result.facts[0].verification_status == VerificationStatus.CONFLICTED


def test_validate_warns_on_low_confidence_without_citation(
    db_session: Session,
    project: Project,
) -> None:
    fact_repo = FactRepository(db_session)
    fact_repo.create(
        ProjectFact(
            project_id=project.id,
            key="bed_count",
            label="床位数",
            value="500",
            confidence=0.3,
        )
    )

    result = FactValidationService(db_session).validate(project.id)

    assert len(result.issues) == 2
    assert any("置信度偏低" in issue for issue in result.issues)
    assert any("缺少来源引用" in issue for issue in result.issues)


def test_validate_skips_rejected_facts(db_session: Session, project: Project) -> None:
    fact = ProjectFact(
        project_id=project.id,
        key="rejected_fact",
        label="已驳回",
        value="",
    )
    fact.reject()
    FactRepository(db_session).create(fact)

    result = FactValidationService(db_session).validate(project.id)

    assert result.issues == []


def test_validate_passes_confirmed_fact(db_session: Session, project: Project) -> None:
    fact = ProjectFact(
        project_id=project.id,
        key="site_area",
        label="用地面积",
        value="12.5 公顷",
        confidence=0.95,
    )
    fact.confirm()
    FactRepository(db_session).create(fact)

    result = FactValidationService(db_session).validate(project.id)

    assert result.issues == []
