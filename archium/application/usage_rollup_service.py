"""Project LLM usage rollup from persisted LLMTrace rows (Topic 08 / BILL-001)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CapabilityUsage:
    capability: str
    call_count: int
    total_tokens: int


@dataclass(frozen=True)
class ProjectUsageRollup:
    """Aggregated token usage for one project (metadata only — no prompts)."""

    project_id: UUID
    call_count: int = 0
    success_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    by_capability: tuple[CapabilityUsage, ...] = ()
    soft_budget_tokens: int = 0
    since: datetime | None = None
    until: datetime | None = None

    @property
    def over_soft_budget(self) -> bool:
        return self.soft_budget_tokens > 0 and self.total_tokens >= self.soft_budget_tokens

    @property
    def budget_ratio(self) -> float | None:
        if self.soft_budget_tokens <= 0:
            return None
        return min(1.0, self.total_tokens / float(self.soft_budget_tokens))

    def display_line(self) -> str:
        if self.call_count <= 0:
            return "尚无 LLM 调用记录"
        return (
            f"{self.call_count} 次调用 · "
            f"{self.total_tokens:,} tokens"
            f"（prompt {self.prompt_tokens:,} / completion {self.completion_tokens:,}）"
        )


class UsageRollupService:
    """Sum LLMTrace tokens by project — soft budget warn only (no hard block)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def rollup_for_project(
        self,
        project_id: UUID,
        *,
        since: datetime | None = None,
        soft_budget_tokens: int | None = None,
        capability_limit: int = 6,
    ) -> ProjectUsageRollup:
        from archium.config.settings import get_settings
        from archium.infrastructure.database.repositories import LLMTraceRepository

        budget = soft_budget_tokens
        if budget is None:
            try:
                budget = int(
                    getattr(get_settings(), "llm_usage_soft_budget_tokens", 500_000)
                )
            except Exception:
                budget = 500_000

        resolved_since = since
        if resolved_since is None:
            # Calendar month window (UTC) — enough for Home strip without Org billing.
            now = datetime.now(UTC)
            resolved_since = datetime(now.year, now.month, 1, tzinfo=UTC)

        agg = LLMTraceRepository(self._session).aggregate_for_project(
            project_id,
            since=resolved_since,
            capability_limit=capability_limit,
        )
        return ProjectUsageRollup(
            project_id=project_id,
            call_count=agg["call_count"],
            success_count=agg["success_count"],
            prompt_tokens=agg["prompt_tokens"],
            completion_tokens=agg["completion_tokens"],
            total_tokens=agg["total_tokens"],
            by_capability=tuple(
                CapabilityUsage(
                    capability=row["capability"],
                    call_count=row["call_count"],
                    total_tokens=row["total_tokens"],
                )
                for row in agg["by_capability"]
            ),
            soft_budget_tokens=max(0, int(budget or 0)),
            since=resolved_since,
            until=datetime.now(UTC),
        )
