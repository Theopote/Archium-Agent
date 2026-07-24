"""Unit tests for materials-aware context evidence gathering."""

from __future__ import annotations

from unittest.mock import MagicMock

from archium.application.context_evidence import (
    build_verified_constraints_block,
    gather_project_evidence,
)
from archium.application.context_intelligence_service import ContextIntelligenceService
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectOriginMode, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.context_intelligence_schemas import (
    ContextAssessmentDraft,
    NextBestActionDraft,
)
from archium.prompts.concept_direction import build_exploration_direction_user_prompt
from archium.prompts.context_intelligence import build_context_assessment_user_prompt


def test_assessment_prompt_includes_evidence_blocks() -> None:
    prompt = build_context_assessment_user_prompt(
        user_text="医院改造",
        project_name="某医院",
        document_count=1,
        document_summaries="- brief.pdf",
        fact_lines="- [已确认] 地点: 西安",
        chunk_excerpts="- [p.1] 现状门诊楼建于1998年",
        gap_lines="- [阻断] 缺少标准事实：建筑面积",
        confirmed_fact_count=1,
        pending_fact_count=0,
        blocking_gap_count=1,
    )
    assert "【已提取/已确认事实】" in prompt
    assert "西安" in prompt
    assert "现状门诊楼" in prompt
    assert "建筑面积" in prompt


def test_exploration_prompt_includes_verified_constraints() -> None:
    prompt = build_exploration_direction_user_prompt(
        project_name="医院",
        idea_text="改扩建",
        count=3,
        verified_constraints_block="- [已确认] 地点: 西安",
    )
    assert "硬约束" in prompt
    assert "西安" in prompt


def test_gather_project_evidence_includes_facts_chunks_gaps(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="医院改造", description="旧楼改造")
    )
    db_session.commit()

    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="location",
            label="地点",
            value="西安",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    )
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="building_area",
            label="建筑面积",
            value="未提取",
            verification_status=VerificationStatus.REJECTED,
        )
    )

    doc = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="site-notes.txt",
            original_path="site-notes.txt",
            stored_path="site-notes.txt",
            file_type=DocumentType.OTHER,
            file_hash="a" * 64,
            size_bytes=12,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    DocumentRepository(db_session).create_chunk(
        DocumentChunk(
            document_id=doc.id,
            project_id=project.id,
            content="现状门诊楼建于1998年，南北向布局。",
            chunk_index=0,
            page_number=1,
            content_type="text",
        )
    )
    db_session.commit()

    pack = gather_project_evidence(db_session, project.id)
    assert pack.document_count == 1
    assert "site-notes.txt" in pack.document_summaries
    assert pack.confirmed_fact_count == 1
    assert "西安" in pack.fact_lines
    assert "未提取" not in pack.fact_lines
    assert "1998" in pack.chunk_excerpts
    assert pack.blocking_gap_count >= 1
    assert pack.has_evidence is True

    constraints = build_verified_constraints_block(db_session, project.id)
    assert "西安" in constraints


def test_assess_and_persist_passes_materials_evidence(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="医院改造", description="旧楼改造")
    )
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="location",
            label="地点",
            value="西安",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    )
    db_session.commit()

    llm = MagicMock()
    llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.5,
        maturity_stage="design_analysis",
        evidence_ratio=0.4,
        assumption_ratio=0.5,
        known={"location": "西安"},
        unknown=["建筑面积"],
        missing_information=["建筑面积"],
        suggested_origin_mode="existing_project",
        understanding_summary="已有地点事实，仍缺面积。",
        actions=[
            NextBestActionDraft(action="ask", reason="确认面积", priority=0),
        ],
    )
    service = ContextIntelligenceService(db_session, llm)
    result = service.assess_and_persist(project.id, "医院旧楼改造")

    assert result.knowledge_state.source == "materials_aware"
    assert result.suggested_origin_mode == ProjectOriginMode.EXISTING_PROJECT
    user_prompt = llm.generate_structured.call_args.args[0].user_prompt
    assert "西安" in user_prompt
    assert "【已提取/已确认事实】" in user_prompt


def test_rule_fallback_uses_confirmed_facts() -> None:
    from archium.application.context_evidence import ProjectEvidencePack

    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("down")
    service = ContextIntelligenceService(MagicMock(), llm)
    pack = ProjectEvidencePack(
        document_count=1,
        document_summaries="- a.pdf",
        fact_lines="- [已确认] 地点: 西安",
        confirmed_fact_count=2,
        extracted_fact_count=1,
        gap_lines="- [阻断] 缺少标准事实：建筑面积",
        blocking_gap_count=1,
    )
    result = service.assess_text(
        "医院改造",
        project_name="医院",
        evidence=pack,
    )
    assert result.suggested_origin_mode == ProjectOriginMode.EXISTING_PROJECT
    assert result.actions[0].action.value == "ask"
    assert any("建筑面积" in item for item in result.knowledge_state.unknown)
