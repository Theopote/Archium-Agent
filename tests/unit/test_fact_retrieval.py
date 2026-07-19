"""Unit tests for hybrid fact ranking in project context."""

from __future__ import annotations

from uuid import uuid4

from archium.application.fact_retrieval import match_fact_keys_from_query, rank_facts_for_context
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact


def _fact(*, key: str, label: str, value: str, confirmed: bool = False) -> ProjectFact:
    status = (
        VerificationStatus.USER_CONFIRMED
        if confirmed
        else VerificationStatus.EXTRACTED
    )
    return ProjectFact(
        project_id=uuid4(),
        key=key,
        label=label,
        value=value,
        verification_status=status,
    )


def test_match_fact_keys_from_query() -> None:
    matched = match_fact_keys_from_query("本次汇报需说明容积率与限高控制")
    assert "plot_ratio" in matched
    assert "height" in matched


def test_rank_facts_for_context_prioritizes_query_and_confirmed() -> None:
    facts = [
        _fact(key="bed_count", label="床位数", value="500"),
        _fact(key="plot_ratio", label="容积率", value="2.5", confirmed=True),
        _fact(key="height", label="建筑高度", value="80"),
    ]
    ranked = rank_facts_for_context(
        facts,
        query="容积率与建筑高度",
        limit=10,
    )
    assert [fact.key for fact in ranked[:2]] == ["plot_ratio", "height"]
