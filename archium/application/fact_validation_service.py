"""Validate persisted project facts before brief generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.domain.enums import VerificationStatus
from archium.domain.fact import FactValue, ProjectFact
from archium.domain.fact_ledger import SEMANTIC_ALIAS_GROUPS, STANDARD_FACT_KEY_MAP
from archium.infrastructure.database.repositories import FactRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="fact_validation")


@dataclass
class FactValidationResult:
    facts: list[ProjectFact] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class FactValidationService:
    """Rule-based validation for project fact quality and conflicts."""

    def __init__(self, session: Session) -> None:
        self._facts = FactRepository(session)

    def validate(self, project_id: UUID) -> FactValidationResult:
        facts = self._facts.list_by_project(project_id)
        issues: list[str] = []

        for fact in facts:
            if fact.verification_status == VerificationStatus.REJECTED:
                continue
            definition = STANDARD_FACT_KEY_MAP.get(fact.key)
            if definition and definition.conflict_group and not fact.conflict_group:
                fact.conflict_group = definition.conflict_group

            if _is_empty_value(fact.value):
                issues.append(f"事实「{fact.label}」值为空")
                fact.mark_conflicted()
                fact.conflict_group = fact.conflict_group or f"empty:{fact.key}"
                self._facts.update(fact)
                continue
            if fact.confidence < 0.5:
                issues.append(
                    f"事实「{fact.label}」置信度偏低 ({fact.confidence:.2f})，建议人工确认"
                )
            if not fact.source_citations and fact.verification_status == VerificationStatus.EXTRACTED:
                issues.append(f"事实「{fact.label}」缺少来源引用")

        issues.extend(self._detect_semantic_conflicts(facts))

        if issues:
            logger.warning("Fact validation for project %s: %d issue(s)", project_id, len(issues))
        else:
            logger.info("Fact validation passed for project %s (%d facts)", project_id, len(facts))

        return FactValidationResult(facts=facts, issues=issues)

    def _detect_semantic_conflicts(self, facts: list[ProjectFact]) -> list[str]:
        by_key = {
            fact.key: fact
            for fact in facts
            if fact.verification_status != VerificationStatus.REJECTED
        }
        issues: list[str] = []

        for alias_group in SEMANTIC_ALIAS_GROUPS:
            present = [by_key[key] for key in alias_group if key in by_key]
            if len(present) < 2:
                continue
            normalized = {_normalize_value(fact.value) for fact in present}
            if len(normalized) == 1:
                continue
            group_id = f"alias:{alias_group[0]}"
            labels = " / ".join(fact.label for fact in present)
            issues.append(f"语义冲突：{labels} 存在不同取值，请人工确认")
            for fact in present:
                fact.mark_conflicted()
                fact.conflict_group = group_id
                self._facts.update(fact)

        grouped: dict[str, list[ProjectFact]] = {}
        for fact in by_key.values():
            if not fact.conflict_group:
                continue
            grouped.setdefault(fact.conflict_group, []).append(fact)

        for group_name, group_facts in grouped.items():
            if group_name.startswith("alias:") or group_name.startswith("empty:"):
                continue
            values = {_normalize_value(fact.value) for fact in group_facts}
            if len(values) <= 1:
                continue
            group_id = group_name or str(uuid4())
            labels = "、".join(fact.label for fact in group_facts)
            issues.append(f"冲突组 {group_name}：{labels} 取值不一致")
            for fact in group_facts:
                fact.mark_conflicted()
                fact.conflict_group = group_id
                self._facts.update(fact)

        return issues


def _is_empty_value(value: FactValue) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _normalize_value(value: FactValue) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value).strip().lower()
