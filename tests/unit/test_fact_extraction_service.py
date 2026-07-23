"""Unit tests for FactExtractionService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.chunk_models import ProjectContextBundle
from archium.application.fact_extraction_service import FactExtractionService
from archium.config.settings import Settings
from archium.domain.document import DocumentChunk
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import FactRepository, ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mock_presentation_responses import FACT_EXTRACTION_JSON


def _fact_extraction_selector(request: LLMRequest) -> str | None:
    if "结构化事实 JSON" in request.user_prompt:
        return FACT_EXTRACTION_JSON
    return None


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="事实提取项目"))


@pytest.fixture
def context_bundle() -> ProjectContextBundle:
    chunk = DocumentChunk(
        document_id=uuid4(),
        project_id=uuid4(),
        chunk_index=0,
        content="项目用地面积约 12.5 公顷，规划床位 500 张。",
        page_number=1,
    )
    return ProjectContextBundle(
        text=f"- [chunk_id={chunk.id}] 项目用地面积约 12.5 公顷，规划床位 500 张。",
        chunks=[chunk],
        document_names={chunk.document_id: "任务书.pdf"},
    )


def test_extract_from_document_creates_metric_facts(
    db_session: Session,
    project: Project,
) -> None:
    chunk = DocumentChunk(
        project_id=project.id,
        document_id=uuid4(),
        chunk_index=0,
        content="规划容积率 2.8，限高 100 米。",
        page_number=2,
    )

    created = FactExtractionService(
        db_session,
        settings=Settings(_env_file=None, fact_extraction_enabled=True),
    ).extract_from_document(
        project.id,
        document_name="指标.docx",
        chunks=[chunk],
    )

    assert created == 2
    facts = FactRepository(db_session).list_by_project(project.id)
    assert {fact.key for fact in facts} == {"plot_ratio", "height"}


def test_extract_from_context_merges_existing_and_adds_missing_via_llm(
    db_session: Session,
    project: Project,
    context_bundle: ProjectContextBundle,
) -> None:
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12.5",
            unit="公顷",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    )
    mock_llm = MockLLMProvider(selector=_fact_extraction_selector)

    facts, created = FactExtractionService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, fact_extraction_enabled=True, llm_api_key="test"),
    ).extract_from_context(project.id, context_bundle)

    assert created == 1
    assert len(facts) == 2
    assert {fact.key for fact in facts} == {"site_area", "bed_count"}
    assert len(mock_llm.calls) == 1


def test_extract_persists_new_facts(
    db_session: Session,
    project: Project,
    context_bundle: ProjectContextBundle,
) -> None:
    mock_llm = MockLLMProvider(selector=_fact_extraction_selector)

    facts, created = FactExtractionService(
        db_session,
        llm=mock_llm,
        settings=Settings(_env_file=None, fact_extraction_enabled=True, llm_api_key="test"),
    ).extract_from_context(project.id, context_bundle)

    assert created >= 2
    assert len(facts) >= 2
    assert "site_area" in {fact.key for fact in facts}
    assert "bed_count" in {fact.key for fact in facts}
    assert len(mock_llm.calls) == 1


def test_upsert_retains_alternate_value_on_key_conflict(
    db_session: Session,
    project: Project,
) -> None:
    """KN-001: unique (project_id, key) must not silently drop conflicting values."""
    facts = FactRepository(db_session)
    service = FactExtractionService(
        db_session,
        settings=Settings(_env_file=None, fact_extraction_enabled=True),
    )
    facts.create(
        ProjectFact(
            project_id=project.id,
            key="plot_ratio",
            label="容积率",
            value="2.5",
            confidence=0.6,
            verification_status=VerificationStatus.EXTRACTED,
        )
    )
    stored, action = service._upsert_fact(
        ProjectFact(
            project_id=project.id,
            key="plot_ratio",
            label="容积率",
            value="2.8",
            confidence=0.5,
        )
    )
    assert action == "conflicted"
    assert stored.value == "2.5"
    assert "2.8" in {str(item) for item in stored.alternate_values}
    reloaded = facts.get_by_project_key(project.id, "plot_ratio")
    assert reloaded is not None
    assert "2.8" in {str(item) for item in reloaded.alternate_values}
