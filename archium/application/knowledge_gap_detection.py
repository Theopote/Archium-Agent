"""Detect gaps in project knowledge before generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.application.knowledge_isolation import CRITICAL_FACT_KEYS
from archium.domain.enums import InformationOrigin, KnowledgeGapStatus, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.fact_ledger import STANDARD_FACT_KEYS
from archium.domain.knowledge_gap import KnowledgeGap
from archium.domain.project_knowledge import ProjectKnowledgeItem


@dataclass(frozen=True)
class KnowledgeGapEntry:
    """A detected gap in project knowledge."""

    gap_id: str
    category: str
    description: str
    why_it_matters: str
    blocking: bool = False
    related_keys: tuple[str, ...] = ()
    source: str = "system"


@dataclass
class KnowledgeGapReport:
    project_id: UUID
    gaps: list[KnowledgeGapEntry] = field(default_factory=list)

    @property
    def blocking_gaps(self) -> list[KnowledgeGapEntry]:
        return [gap for gap in self.gaps if gap.blocking]

    @property
    def gap_count(self) -> int:
        return len(self.gaps)


def detect_knowledge_gaps(
    project_id: UUID,
    *,
    facts: list[ProjectFact],
    knowledge_items: list[ProjectKnowledgeItem] | None = None,
    mission_gaps: list[KnowledgeGap] | None = None,
    required_fact_keys: tuple[str, ...] | None = None,
) -> KnowledgeGapReport:
    """Identify missing or unconfirmed knowledge before formal generation."""
    report = KnowledgeGapReport(project_id=project_id)
    active_facts = [f for f in facts if f.verification_status != VerificationStatus.REJECTED]
    by_key = {fact.key: fact for fact in active_facts}

    keys_to_check = required_fact_keys or tuple(d.key for d in STANDARD_FACT_KEYS)
    for key in keys_to_check:
        definition = next((d for d in STANDARD_FACT_KEYS if d.key == key), None)
        label = definition.label if definition else key
        fact = by_key.get(key)
        if fact is None:
            report.gaps.append(
                KnowledgeGapEntry(
                    gap_id=f"missing:{key}",
                    category="missing_fact",
                    description=f"缺少标准事实：{label}",
                    why_it_matters="正式汇报页不应虚构关键项目参数。",
                    blocking=key in CRITICAL_FACT_KEYS,
                    related_keys=(key,),
                )
            )
            continue
        if fact.verification_status == VerificationStatus.CONFLICTED:
            report.gaps.append(
                KnowledgeGapEntry(
                    gap_id=f"conflict:{key}",
                    category="conflict",
                    description=f"事实冲突：{label}",
                    why_it_matters="冲突数据进入页面会造成事实错误。",
                    blocking=True,
                    related_keys=(key,),
                )
            )
        elif key in CRITICAL_FACT_KEYS and not fact.is_confirmed:
            report.gaps.append(
                KnowledgeGapEntry(
                    gap_id=f"unconfirmed:{key}",
                    category="unconfirmed_critical",
                    description=f"待确认关键事实：{label}",
                    why_it_matters="面积、高度、文保级别等关键参数需用户确认。",
                    blocking=True,
                    related_keys=(key,),
                )
            )

    items = knowledge_items or []
    for item in items:
        if item.is_rejected:
            continue
        if item.is_reference_only:
            continue
        if not item.source_citations and item.origin == InformationOrigin.PUBLIC_RESEARCH:
            report.gaps.append(
                KnowledgeGapEntry(
                    gap_id=f"uncited:{item.id}",
                    category="uncited_external",
                    description=f"外部信息缺少引用：{item.statement[:80]}",
                    why_it_matters="公开资料不得无来源进入正式页面。",
                    blocking=True,
                )
            )

    if mission_gaps:
        for gap in mission_gaps:
            if gap.status != KnowledgeGapStatus.OPEN:
                continue
            report.gaps.append(
                KnowledgeGapEntry(
                    gap_id=f"mission:{gap.id}",
                    category="mission_gap",
                    description=gap.question,
                    why_it_matters=gap.why_it_matters,
                    blocking=gap.blocking,
                    source="mission",
                )
            )

    return report
