"""Review issue analytics keyed by stable rule_code."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.enums import ReviewStatus
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import repair_strategy_for_rule


@dataclass(frozen=True)
class RuleCodeStats:
    """Aggregated counts for one rule_code within a presentation or workflow pass."""

    rule_code: str
    total: int
    open: int
    resolved: int
    dismissed: int
    repair_strategy: str

    @property
    def acted_count(self) -> int:
        return self.resolved + self.dismissed

    @property
    def dismiss_rate(self) -> float | None:
        """Share of user-closed issues marked as ignored — proxy for false positives."""
        if self.acted_count == 0:
            return None
        return self.dismissed / self.acted_count


def summarize_rule_codes(issues: list[ReviewIssue]) -> list[RuleCodeStats]:
    """Summarize review issues by rule_code for UI stats and tuning."""
    buckets: dict[str, dict[str, int]] = {}

    for issue in issues:
        counts = buckets.setdefault(
            issue.rule_code,
            {"total": 0, "open": 0, "resolved": 0, "dismissed": 0},
        )
        counts["total"] += 1
        if issue.status == ReviewStatus.OPEN:
            counts["open"] += 1
        elif issue.status == ReviewStatus.RESOLVED:
            counts["resolved"] += 1
        elif issue.status == ReviewStatus.DISMISSED:
            counts["dismissed"] += 1

    return [
        RuleCodeStats(
            rule_code=rule_code,
            total=counts["total"],
            open=counts["open"],
            resolved=counts["resolved"],
            dismissed=counts["dismissed"],
            repair_strategy=repair_strategy_for_rule(rule_code),
        )
        for rule_code, counts in sorted(buckets.items(), key=lambda item: (-item[1]["total"], item[0]))
    ]
