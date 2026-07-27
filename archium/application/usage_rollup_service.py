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
        by_capability_raw = agg.get("by_capability")
        by_capability_rows: list[dict[str, object]] = (
            list(by_capability_raw) if isinstance(by_capability_raw, list) else []
        )
        return ProjectUsageRollup(
            project_id=project_id,
            call_count=_as_int(agg.get("call_count")),
            success_count=_as_int(agg.get("success_count")),
            prompt_tokens=_as_int(agg.get("prompt_tokens")),
            completion_tokens=_as_int(agg.get("completion_tokens")),
            total_tokens=_as_int(agg.get("total_tokens")),
            by_capability=tuple(
                CapabilityUsage(
                    capability=str(row.get("capability") or "unknown"),
                    call_count=_as_int(row.get("call_count")),
                    total_tokens=_as_int(row.get("total_tokens")),
                )
                for row in by_capability_rows
                if isinstance(row, dict)
            ),
            soft_budget_tokens=max(0, _as_int(budget)),
            since=resolved_since,
            until=datetime.now(UTC),
        )


def _as_int(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0
