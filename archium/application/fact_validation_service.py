"""Validate persisted project facts before brief generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.enums import VerificationStatus
from archium.domain.fact import FactValue, ProjectFact
from archium.infrastructure.database.repositories import FactRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="fact_validation")


@dataclass
class FactValidationResult:
    facts: list[ProjectFact] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class FactValidationService:
    """Rule-based validation for project fact quality."""

    def __init__(self, session: Session) -> None:
        self._facts = FactRepository(session)

    def validate(self, project_id: UUID) -> FactValidationResult:
        facts = self._facts.list_by_project(project_id)
        issues: list[str] = []

        for fact in facts:
            if fact.verification_status == VerificationStatus.REJECTED:
                continue
            if _is_empty_value(fact.value):
                issues.append(f"事实「{fact.label}」值为空")
                fact.mark_conflicted()
                self._facts.update(fact)
                continue
            if fact.confidence < 0.5:
                issues.append(
                    f"事实「{fact.label}」置信度偏低 ({fact.confidence:.2f})，建议人工确认"
                )
            if not fact.source_citations and fact.verification_status == VerificationStatus.EXTRACTED:
                issues.append(f"事实「{fact.label}」缺少来源引用")

        if issues:
            logger.warning("Fact validation for project %s: %d issue(s)", project_id, len(issues))
        else:
            logger.info("Fact validation passed for project %s (%d facts)", project_id, len(facts))

        return FactValidationResult(facts=facts, issues=issues)


def _is_empty_value(value: FactValue) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False
