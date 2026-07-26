"""DOM-008 / KN-002 — Fact ↔ Knowledge ↔ Manuscript ID links and lossy mapping."""

from __future__ import annotations

from uuid import uuid4

from archium.application.fact_knowledge_manuscript_mapping import (
    DROPPED_FACT_TO_KNOWLEDGE,
    DROPPED_KNOWLEDGE_TO_MANUSCRIPT,
    knowledge_item_to_evidence,
    knowledge_item_to_manuscript_fact,
    link_invariant_issues,
    project_fact_to_knowledge_item,
)
from archium.domain.citation import Citation
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation


def test_fact_to_knowledge_sets_linked_fact_id_and_drop_warnings() -> None:
    fact = ProjectFact(
        project_id=uuid4(),
        key="site_area",
        label="用地面积",
        value=6.8,
        unit="万㎡",
        confidence=0.9,
        verification_status=VerificationStatus.USER_CONFIRMED,
        alternate_values=[7.0],
        source_citations=[
            Citation(document_id=uuid4(), document_name="指标.pdf", quote="6.8")
        ],
    )
    item, result = project_fact_to_knowledge_item(fact)

    assert item.linked_fact_id == fact.id
    assert item.id == fact.id
    assert "用地面积" in item.statement
    dropped = set(result.warnings)
    for name in DROPPED_FACT_TO_KNOWLEDGE:
        assert f"DROPPED_FACT_{name}" in dropped


def test_knowledge_to_manuscript_copies_ids_and_drop_warnings() -> None:
    fact_id = uuid4()
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="绿地率 35%",
        origin=InformationOrigin.USER_CONFIRMED,
        reliability=InformationReliability.CONFIRMED,
        status=KnowledgeItemStatus.CONFIRMED,
        category="metrics",
        conflict_group="g1",
        linked_fact_id=fact_id,
        design_knowledge=None,
    )
    mf, result = knowledge_item_to_manuscript_fact(item, verified=True)

    assert mf.knowledge_item_id == item.id
    assert mf.linked_fact_id == fact_id
    assert mf.source_id == str(item.id)
    dropped = set(result.warnings)
    for name in DROPPED_KNOWLEDGE_TO_MANUSCRIPT:
        assert f"DROPPED_KNOWLEDGE_{name}" in dropped

    evidence = knowledge_item_to_evidence(item, verified=True, confidence=1.0)
    assert evidence.knowledge_item_id == item.id
    assert evidence.linked_fact_id == fact_id


def test_three_hop_traceability_invariant() -> None:
    fact = ProjectFact(
        project_id=uuid4(),
        key="green_ratio",
        label="绿地率",
        value="35%",
        verification_status=VerificationStatus.USER_CONFIRMED,
    )
    item, _ = project_fact_to_knowledge_item(fact)
    mf, _ = knowledge_item_to_manuscript_fact(item, verified=True)

    assert link_invariant_issues(fact=fact, knowledge=item, manuscript_fact=mf) == []
    assert mf.linked_fact_id == fact.id
    assert mf.knowledge_item_id == item.id


def test_link_invariant_detects_break() -> None:
    fact = ProjectFact(
        project_id=uuid4(),
        key="height",
        label="高度",
        value=24,
        verification_status=VerificationStatus.EXTRACTED,
    )
    item, _ = project_fact_to_knowledge_item(fact)
    mf, _ = knowledge_item_to_manuscript_fact(item, verified=False)
    broken = mf.model_copy(update={"linked_fact_id": uuid4()})

    issues = link_invariant_issues(fact=fact, knowledge=item, manuscript_fact=broken)
    assert any("linked_fact_id" in msg for msg in issues)


def test_build_from_knowledge_propagates_linked_fact_id(tmp_path) -> None:
    import archium.infrastructure.database.models  # noqa: F401
    from archium.application.presentation_manuscript_service import (
        PresentationManuscriptService,
    )
    from archium.infrastructure.database.base import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'ms-link.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    project_id = uuid4()
    fact_id = uuid4()
    doc_id = uuid4()
    item = ProjectKnowledgeItem(
        project_id=project_id,
        statement="基地面积 6.8 万㎡",
        origin=InformationOrigin.USER_UPLOAD,
        reliability=InformationReliability.CONFIRMED,
        source_citations=[
            SourceCitation(document_id=doc_id, document_name="设计说明.pdf")
        ],
        status=KnowledgeItemStatus.CONFIRMED,
        linked_fact_id=fact_id,
    )
    manuscript = PresentationManuscriptService(session).build_from_knowledge(
        project_id=project_id,
        title="链接手稿",
        project_summary="院区",
        narrative_thesis="入口优先",
        knowledge_items=[item],
        presentation_id=uuid4(),
    )
    mf = manuscript.verified_facts[0]
    assert mf.knowledge_item_id == item.id
    assert mf.linked_fact_id == fact_id
    ev = manuscript.evidence_catalog[0]
    assert ev.knowledge_item_id == item.id
    assert ev.linked_fact_id == fact_id
    session.close()
