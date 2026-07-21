"""Unit tests for PresentationManuscript."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.outline_service import outline_from_manuscript
from archium.application.presentation_manuscript_service import (
    PresentationManuscriptService,
    outline_plan_from_manuscript,
)
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
)
from archium.domain.presentation_manuscript import (
    EvidenceItem,
    ManuscriptFact,
    ManuscriptSection,
    PresentationManuscript,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Minimal in-memory-ish session via project test helpers if available."""
    pytest.importorskip("sqlalchemy")
    import archium.infrastructure.database.models  # noqa: F401
    from archium.infrastructure.database.base import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'ms.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_manuscript_excludes_reference_only_knowledge(db_session) -> None:
    project_id = uuid4()
    doc_id = uuid4()
    project_item = ProjectKnowledgeItem(
        project_id=project_id,
        statement="基地面积 6.8 万㎡",
        origin=InformationOrigin.USER_UPLOAD,
        reliability=InformationReliability.CONFIRMED,
        source_citations=[
            SourceCitation(document_id=doc_id, document_name="设计说明.pdf")
        ],
        status=KnowledgeItemStatus.CONFIRMED,
    )
    reference_item = ProjectKnowledgeItem(
        project_id=project_id,
        statement="某案例医院入口采用环形车道",
        origin=InformationOrigin.REFERENCE_CASE,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[
            SourceCitation(document_id=doc_id, document_name="案例集.pdf")
        ],
        applies_to_current_project=False,
        status=KnowledgeItemStatus.ACTIVE,
    )
    service = PresentationManuscriptService(db_session)
    manuscript = service.build_from_knowledge(
        project_id=project_id,
        title="测试手稿",
        project_summary="院区更新",
        narrative_thesis="入口交通必须优先治理",
        knowledge_items=[project_item, reference_item],
        presentation_id=uuid4(),
    )
    assert any("6.8" in f.statement for f in manuscript.verified_facts)
    assert not any("环形车道" in f.statement for f in manuscript.verified_facts)
    assert manuscript.unsupported_claims
    assert all(e.asset_origin != "reference_template" for e in manuscript.evidence_catalog)


def test_manuscript_facts_are_traceable(db_session) -> None:
    project_id = uuid4()
    doc_id = uuid4()
    item = ProjectKnowledgeItem(
        project_id=project_id,
        statement="绿地率 35%",
        origin=InformationOrigin.USER_CONFIRMED,
        reliability=InformationReliability.CONFIRMED,
        source_citations=[
            SourceCitation(document_id=doc_id, document_name="指标表.xlsx", quote="35%")
        ],
        status=KnowledgeItemStatus.CONFIRMED,
    )
    manuscript = PresentationManuscriptService(db_session).build_from_knowledge(
        project_id=project_id,
        title="指标手稿",
        project_summary="指标",
        narrative_thesis="指标完整",
        knowledge_items=[item],
        presentation_id=uuid4(),
    )
    fact = manuscript.verified_facts[0]
    assert fact.verified is True
    assert fact.citation_ids
    assert manuscript.citations
    assert manuscript.citations[0].citation.document_id == doc_id


def test_manuscript_rejects_citations_without_document_id(db_session) -> None:
    """Non-empty but document-less source_citations must not enter verified_facts."""
    project_id = uuid4()
    invalid = ProjectKnowledgeItem(
        project_id=project_id,
        statement="外部网页提到容积率约 2.0",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[
            SourceCitation(url="https://example.com/report", source_title="网页摘录")
        ],
        status=KnowledgeItemStatus.ACTIVE,
    )
    upload_without_doc = ProjectKnowledgeItem(
        project_id=project_id,
        statement="用户粘贴但未绑定文档的指标",
        origin=InformationOrigin.USER_UPLOAD,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[
            SourceCitation(url="https://example.com/note", source_title="无文档")
        ],
        status=KnowledgeItemStatus.ACTIVE,
    )
    manuscript = PresentationManuscriptService(db_session).build_from_knowledge(
        project_id=project_id,
        title="无效引用手稿",
        project_summary="测试",
        narrative_thesis="不得收录不可追溯事实",
        knowledge_items=[invalid, upload_without_doc],
        presentation_id=uuid4(),
    )
    assert manuscript.verified_facts == []
    assert any("有效可追溯引用" in msg for msg in manuscript.missing_information)


def test_manuscript_allows_user_confirmed_without_document_citation(db_session) -> None:
    project_id = uuid4()
    confirmed = ProjectKnowledgeItem(
        project_id=project_id,
        statement="业主确认一期投资上限 8.5 亿",
        origin=InformationOrigin.USER_CONFIRMED,
        reliability=InformationReliability.CONFIRMED,
        source_citations=[],
        status=KnowledgeItemStatus.CONFIRMED,
    )
    manuscript = PresentationManuscriptService(db_session).build_from_knowledge(
        project_id=project_id,
        title="人工确认手稿",
        project_summary="测试",
        narrative_thesis="人工确认可收录",
        knowledge_items=[confirmed],
        presentation_id=uuid4(),
    )
    assert len(manuscript.verified_facts) == 1
    assert manuscript.verified_facts[0].statement.startswith("业主确认")
    assert manuscript.verified_facts[0].verified is True
    assert manuscript.verified_facts[0].citation_ids == []


def test_outline_reads_manuscript() -> None:
    presentation_id = uuid4()
    manuscript = PresentationManuscript(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="手稿标题",
        project_summary="摘要",
        narrative_thesis="核心论点",
        sections=[
            ManuscriptSection(
                id="s1",
                title="现状",
                purpose="说明问题",
                argument="入口拥堵",
                key_points=["车行冲突", "人行不足"],
                order=0,
            ),
            ManuscriptSection(
                id="s2",
                title="策略",
                purpose="提出对策",
                argument="分流改造",
                key_points=["环形组织"],
                order=1,
            ),
        ],
        verified_facts=[
            ManuscriptFact(
                statement="基地东侧道路饱和",
                source_id="k1",
                verified=True,
            )
        ],
        evidence_catalog=[
            EvidenceItem(
                evidence_type="project_photo",
                summary="入口照片",
                source_id="a1",
                verified=True,
                asset_origin="project_upload",
            )
        ],
    )
    outline = outline_from_manuscript(manuscript)
    assert outline.manuscript_id == manuscript.id
    assert outline.presentation_id == presentation_id
    assert len(outline.sections) == 2
    assert outline.sections[0].title == "现状"
    assert outline.thesis == "核心论点"

    # Same via pure helper
    outline2 = outline_plan_from_manuscript(manuscript)
    assert outline2.manuscript_id == manuscript.id
