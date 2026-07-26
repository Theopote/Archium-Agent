"""Topic 08 — LLM usage rollup (BILL-001) + soft budget (BILL-002 thin)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from archium.application.usage_rollup_service import UsageRollupService
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    LLMTraceRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.trace import LLMTrace


def _trace(
    project_id,
    *,
    tokens: int,
    capability: str = "mission",
    prompt: int | None = None,
    completion: int | None = None,
) -> LLMTrace:
    return LLMTrace(
        request_id=uuid4().hex[:12],
        provider="openai_compatible",
        model="test-model",
        capability=capability,
        project_id=str(project_id),
        prompt_tokens=prompt if prompt is not None else tokens // 2,
        completion_tokens=completion if completion is not None else tokens - tokens // 2,
        total_tokens=tokens,
        latency_ms=10.0,
        success=True,
    )


def test_usage_rollup_sums_tokens_and_capabilities(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="用量项目"))
    repo = LLMTraceRepository(db_session)
    repo.create_from_trace(_trace(project.id, tokens=100, capability="mission"))
    repo.create_from_trace(_trace(project.id, tokens=50, capability="mission"))
    repo.create_from_trace(_trace(project.id, tokens=80, capability="research"))
    db_session.flush()

    rollup = UsageRollupService(db_session).rollup_for_project(
        project.id,
        since=datetime.now(UTC) - timedelta(days=1),
        soft_budget_tokens=1_000_000,
    )
    assert rollup.call_count == 3
    assert rollup.total_tokens == 230
    assert rollup.prompt_tokens > 0
    caps = {item.capability: item.total_tokens for item in rollup.by_capability}
    assert caps["mission"] == 150
    assert caps["research"] == 80
    assert rollup.over_soft_budget is False
    assert "230" in rollup.display_line().replace(",", "")


def test_soft_budget_warns_when_exceeded(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="超配额"))
    LLMTraceRepository(db_session).create_from_trace(
        _trace(project.id, tokens=600)
    )
    db_session.flush()

    rollup = UsageRollupService(db_session).rollup_for_project(
        project.id,
        since=datetime.now(UTC) - timedelta(hours=1),
        soft_budget_tokens=500,
    )
    assert rollup.over_soft_budget is True
    assert rollup.budget_ratio == 1.0


def test_soft_budget_disabled_when_zero(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="无配额"))
    LLMTraceRepository(db_session).create_from_trace(
        _trace(project.id, tokens=9999)
    )
    db_session.flush()
    rollup = UsageRollupService(db_session).rollup_for_project(
        project.id,
        soft_budget_tokens=0,
    )
    assert rollup.over_soft_budget is False
    assert rollup.budget_ratio is None
