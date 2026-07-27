"""Unit tests for KnowledgeState claim index bridge."""

from __future__ import annotations

from uuid import uuid4

from archium.application.context.knowledge_claim_index import (
    claims_from_evidence,
    merge_claim_index_into_state,
    unknowns_from_evidence,
)
from archium.application.context_evidence import ProjectEvidencePack
from archium.application.knowledge_gap_detection import KnowledgeGapEntry
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    KnowledgeItemStatus,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.intent.knowledge_claim import KnowledgeClaimKind
from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_knowledge import ProjectKnowledgeItem


def test_claims_from_facts_and_knowledge_items() -> None:
    project_id = uuid4()
    fact = ProjectFact(
        project_id=project_id,
        key="location",
        label="地点",
        value="西安",
        verification_status=VerificationStatus.USER_CONFIRMED,
    )
    item = ProjectKnowledgeItem(
        project_id=project_id,
        statement="院区总平面需保留北侧树木",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.HIGH_CONFIDENCE,
        status=KnowledgeItemStatus.ACTIVE,
        category="site",
    )
    claims = claims_from_evidence(
        facts=[fact],
        knowledge_items=[item],
        llm_known={"location": "西安", "type": "医院"},
    )
    kinds = {c.kind for c in claims}
    assert KnowledgeClaimKind.FACT in kinds
    assert KnowledgeClaimKind.KNOWLEDGE_ITEM in kinds
    assert KnowledgeClaimKind.ASSESSMENT in kinds
    fact_claim = next(c for c in claims if c.kind == KnowledgeClaimKind.FACT)
    assert fact_claim.fact_id == fact.id
    assert fact_claim.confirmed is True
    assert any(c.key == "type" for c in claims)


def test_unknowns_prefer_structured_gaps() -> None:
    gaps = [
        KnowledgeGapEntry(
            gap_id="missing:building_area",
            category="missing_fact",
            description="缺少标准事实：建筑面积",
            why_it_matters="正式汇报需要面积",
            blocking=True,
            related_keys=("building_area",),
        )
    ]
    unknowns = unknowns_from_evidence(
        gaps=gaps,
        llm_unknown=["建筑面积", "目标用户"],
    )
    assert unknowns[0].blocking is True
    assert unknowns[0].related_keys == ["building_area"]
    assert any(u.description == "目标用户" for u in unknowns)
    # LLM duplicate of gap text should not double-count
    assert sum(1 for u in unknowns if "建筑面积" in u.description) == 1


def test_merge_claim_index_drops_stale_standard_fact_llm_unknowns() -> None:
    project_id = uuid4()
    pack = ProjectEvidencePack(
        indexed_gaps=(
            KnowledgeGapEntry(
                gap_id="missing:main_function",
                category="missing_fact",
                description="缺少标准事实：主要功能",
                why_it_matters="x",
                blocking=False,
                related_keys=("main_function",),
            ),
        ),
    )
    state = KnowledgeState(
        unknown=[
            "缺少标准事实：床位数",
            "缺少标准事实：容积率",
            "甲方诉求尚未明确",
        ],
        completeness_score=0.1,
    )
    merged = merge_claim_index_into_state(state, pack)
    descriptions = [item.description for item in merged.open_unknowns]
    assert "缺少标准事实：主要功能" in descriptions
    assert not any("床位数" in item for item in descriptions)
    assert not any("容积率" in item for item in descriptions)
    assert any("甲方诉求尚未明确" in item for item in descriptions)


def test_merge_claim_index_into_state_sets_counts() -> None:
    project_id = uuid4()
    fact = ProjectFact(
        project_id=project_id,
        key="location",
        label="地点",
        value="西安",
        verification_status=VerificationStatus.USER_CONFIRMED,
    )
    pack = ProjectEvidencePack(
        document_count=1,
        confirmed_fact_count=1,
        knowledge_item_count=0,
        indexed_facts=(fact,),
        indexed_gaps=(
            KnowledgeGapEntry(
                gap_id="missing:building_area",
                category="missing_fact",
                description="缺少标准事实：建筑面积",
                why_it_matters="x",
                blocking=True,
                related_keys=("building_area",),
            ),
        ),
    )
    state = KnowledgeState(
        known={"type": "医院"},
        unknown=["规模"],
        completeness_score=0.4,
    )
    merged = merge_claim_index_into_state(state, pack)
    assert merged.claims
    assert merged.open_unknowns
    assert merged.known.get("location") == "西安"
    assert merged.known.get("type") == "医院"
    assert merged.fact_count == 1
    assert merged.cognition_stale is False
