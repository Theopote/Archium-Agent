"""Unit tests for knowledge isolation rules."""

from __future__ import annotations

from uuid import uuid4

from archium.application.knowledge_isolation import (
    fact_to_knowledge_item,
    filter_generation_facts,
    is_eligible_for_generation,
    is_reference_document,
)
from archium.domain.citation import Citation
from archium.domain.enums import (
    DocumentPurpose,
    InformationOrigin,
    InformationReliability,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation


def test_reference_case_knowledge_not_eligible_for_generation() -> None:
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="某参考村落的游客量",
        origin=InformationOrigin.REFERENCE_CASE,
        reliability=InformationReliability.HIGH_CONFIDENCE,
        applies_to_current_project=False,
    )
    assert not is_eligible_for_generation(item)


def test_inference_requires_confirmation_before_generation() -> None:
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="推测建筑面积约 5000 ㎡",
        origin=InformationOrigin.SYSTEM_INFERENCE,
        reliability=InformationReliability.INFERENCE,
        requires_user_confirmation=True,
    )
    assert not is_eligible_for_generation(item)


def test_public_research_without_citation_not_eligible() -> None:
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="某政策文件要求",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[],
    )
    assert not is_eligible_for_generation(item)


def test_confirmed_public_research_with_citation_is_eligible() -> None:
    item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="历史文化名村保护条例",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.HIGH_CONFIDENCE,
        source_citations=[
            SourceCitation(
                url="https://example.gov.cn/policy",
                source_title="名村保护条例",
            )
        ],
    )
    assert is_eligible_for_generation(item)


def test_facts_from_reference_documents_are_filtered() -> None:
    doc_id = uuid4()
    facts = [
        ProjectFact(
            project_id=uuid4(),
            key="site_area",
            label="用地面积",
            value="12",
            unit="公顷",
            verification_status=VerificationStatus.EXTRACTED,
            source_citations=[
                Citation(
                    document_id=doc_id,
                    document_name="参考案例.pdf",
                )
            ],
        )
    ]
    filtered = filter_generation_facts(facts, reference_document_ids={str(doc_id)})
    assert filtered == []


def test_unconfirmed_critical_fact_is_filtered() -> None:
    facts = [
        ProjectFact(
            project_id=uuid4(),
            key="building_area",
            label="建筑面积",
            value="5000",
            unit="㎡",
            verification_status=VerificationStatus.EXTRACTED,
        )
    ]
    filtered = filter_generation_facts(facts)
    assert filtered == []


def test_reference_document_metadata_detection() -> None:
    assert is_reference_document({"purpose": DocumentPurpose.REFERENCE_CASE.value})
    assert not is_reference_document({"purpose": DocumentPurpose.PROJECT_MATERIAL.value})


def test_fact_to_knowledge_item_marks_inference() -> None:
    fact = ProjectFact(
        project_id=uuid4(),
        key="main_function",
        label="主要功能",
        value="文化展示",
        verification_status=VerificationStatus.INFERRED,
    )
    item = fact_to_knowledge_item(fact)
    assert item.origin == InformationOrigin.SYSTEM_INFERENCE
    assert item.reliability == InformationReliability.INFERENCE
