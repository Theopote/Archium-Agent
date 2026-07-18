"""Professional consistency validation for ProjectMission domain models.

Parser converts LLM drafts → domain models. This service validates domain models
for architectural-planning consistency (not draft fabrication checks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.domain.enums import (
    KnowledgeGapStatus,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    ValidationSeverity,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import ProjectMission

_FULL_DESIGN_DEPTHS = frozenset(
    {
        ServiceDepth.CONCEPT_DESIGN,
        ServiceDepth.SCHEMATIC_SUPPORT,
    }
)

_CONSULTING_NATURES = frozenset(
    {
        TaskNature.CONSULTING,
        TaskNature.TECHNICAL_STUDY,
        TaskNature.ASSESSMENT,
        TaskNature.STRATEGY,
        TaskNature.RESEARCH,
    }
)

_QUESTION_MARKERS = ("?", "？", "吗", "呢", "如何", "怎样", "是否", "何", "哪", "什么", "为何")


@dataclass(frozen=True)
class MissionValidationIssue:
    """Stable, machine-readable validation finding."""

    rule_code: str
    severity: ValidationSeverity
    message: str
    field: str | None = None
    fields: tuple[str, ...] = ()
    suggestion: str | None = None
    recoverable: bool = True

    def to_dict(self) -> dict:
        tagged = list(dict.fromkeys([*( [self.field] if self.field else [] ), *self.fields]))
        return {
            "rule_code": self.rule_code,
            "severity": self.severity.value,
            "field": self.field,
            "fields": tagged,
            "message": self.message,
            "suggestion": self.suggestion,
            "recoverable": self.recoverable,
        }


@dataclass
class MissionValidationReport:
    """Result of professional consistency checks on a ProjectMission.

    Underlying store is ``issues``. String lists remain as derived convenience
    properties for UI / workflow / live-eval compatibility.
    """

    issues: list[MissionValidationIssue] = field(default_factory=list)
    blocking_gap_ids: list[UUID] = field(default_factory=list)

    def add(self, issue: MissionValidationIssue) -> None:
        self.issues.append(issue)

    @property
    def recoverable_errors(self) -> list[str]:
        return [
            item.message
            for item in self.issues
            if item.severity == ValidationSeverity.ERROR and item.recoverable
        ]

    @property
    def fatal_errors(self) -> list[str]:
        return [
            item.message
            for item in self.issues
            if item.severity == ValidationSeverity.FATAL or not item.recoverable
        ]

    @property
    def warnings(self) -> list[str]:
        return [
            item.message
            for item in self.issues
            if item.severity == ValidationSeverity.WARNING
        ]

    @property
    def suggestions(self) -> list[str]:
        return [
            item.suggestion
            for item in self.issues
            if item.suggestion
            and item.severity
            in {ValidationSeverity.WARNING, ValidationSeverity.SUGGESTION, ValidationSeverity.ERROR}
        ]

    @property
    def inconsistent_fields(self) -> list[str]:
        tagged: list[str] = []
        for item in self.issues:
            if item.field:
                tagged.append(item.field)
            tagged.extend(item.fields)
        return list(dict.fromkeys(tagged))

    @property
    def errors(self) -> list[str]:
        return list(self.recoverable_errors) + list(self.fatal_errors)

    @property
    def ok(self) -> bool:
        return not self.recoverable_errors and not self.fatal_errors

    @property
    def needs_correction(self) -> bool:
        return bool(self.recoverable_errors) and not self.fatal_errors

    @property
    def is_fatal(self) -> bool:
        return bool(self.fatal_errors)

    def to_dict(self) -> dict:
        return {
            "issues": [item.to_dict() for item in self.issues],
            "recoverable_errors": list(self.recoverable_errors),
            "fatal_errors": list(self.fatal_errors),
            "errors": self.errors,
            "warnings": list(self.warnings),
            "suggestions": list(self.suggestions),
            "blocking_gap_ids": [str(item) for item in self.blocking_gap_ids],
            "inconsistent_fields": list(self.inconsistent_fields),
            "ok": self.ok,
            "needs_correction": self.needs_correction,
            "is_fatal": self.is_fatal,
        }


class MissionValidationService:
    """Validate mission domain models for professional planning consistency."""

    def validate(
        self,
        mission: ProjectMission,
        *,
        knowledge_gaps: list[KnowledgeGap] | None = None,
        clarifying_questions: list[ClarifyingQuestion] | None = None,
        facts: list[ProjectFact] | None = None,
    ) -> MissionValidationReport:
        report = MissionValidationReport()
        gaps = knowledge_gaps or []
        questions = clarifying_questions or []
        fact_list = facts or []

        self._check_required_fields(mission, report)
        self._check_scope_conflict(mission, report)
        self._check_service_depth(mission, report)
        self._check_consulting_vs_full_design(mission, report)
        self._check_blocking_gaps(gaps, questions, report)
        self._check_decisions_and_stakeholders(mission, report)
        self._check_confidence_vs_unknowns(mission, report)
        self._check_confirmed_constraints(mission, fact_list, report)
        self._check_evaluation_criteria(mission, report)
        self._check_design_questions(mission, report)
        return report

    def _check_required_fields(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if not mission.task_statement.strip():
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.EMPTY_TASK_STATEMENT",
                    severity=ValidationSeverity.ERROR,
                    field="task_statement",
                    message="任务陈述为空",
                    recoverable=True,
                )
            )
        if not mission.task_natures:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.MISSING_TASK_NATURE",
                    severity=ValidationSeverity.ERROR,
                    field="task_natures",
                    message="任务性质（task_natures）不能为空，请至少选择一项",
                    recoverable=True,
                )
            )
        if not mission.requested_service_depths:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.MISSING_SERVICE_DEPTH",
                    severity=ValidationSeverity.WARNING,
                    field="requested_service_depths",
                    message="未标注服务深度（requested_service_depths），后续工作路径可能偏泛",
                    suggestion="建议补充 PROJECT_DIAGNOSIS / CONCEPT_PLANNING 等服务深度",
                    recoverable=True,
                )
            )

    def _check_scope_conflict(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        in_scope = {_normalize_scope(item) for item in mission.in_scope if item.strip()}
        out_scope = {_normalize_scope(item) for item in mission.out_of_scope if item.strip()}
        overlap = sorted(in_scope & out_scope)
        if overlap:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.SCOPE_CONFLICT",
                    severity=ValidationSeverity.ERROR,
                    field="in_scope",
                    fields=("out_of_scope",),
                    message="工作范围与排除范围冲突：" + "、".join(overlap),
                    suggestion="从 in_scope 或 out_of_scope 中移除冲突项",
                    recoverable=True,
                )
            )

    def _check_service_depth(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        depths = set(mission.requested_service_depths)
        if (
            ServiceDepth.TASK_INTERPRETATION in depths
            and len(depths) == 1
            and mission.task_natures
            and TaskNature.NEW_BUILD in mission.task_natures
        ):
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.SHALLOW_DEPTH_FOR_NEW_BUILD",
                    severity=ValidationSeverity.WARNING,
                    field="requested_service_depths",
                    message="任务性质含新建，但服务深度仅有任务解读，可能低估所需工作深度",
                    recoverable=True,
                )
            )

    def _check_consulting_vs_full_design(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        natures = set(mission.task_natures)
        depths = set(mission.requested_service_depths)
        out_text = " ".join(mission.out_of_scope)
        statement = f"{mission.task_statement} {mission.title}"

        consulting_signal = bool(natures & _CONSULTING_NATURES) or any(
            token in statement for token in ("专项", "咨询", "建议", "诊断", "评估")
        )
        excludes_full_design = any(
            token in out_text for token in ("施工图", "扩初", "完整设计", "设备选型", "招标图")
        )
        full_design_depth = bool(depths & _FULL_DESIGN_DEPTHS)
        misclassified_new_build = (
            TaskNature.NEW_BUILD in natures
            and consulting_signal
            and excludes_full_design
        )

        if consulting_signal and full_design_depth and excludes_full_design:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.CONSULTING_SCOPE_EXPANSION",
                    severity=ValidationSeverity.WARNING,
                    field="task_natures",
                    fields=("requested_service_depths",),
                    message=(
                        "专项咨询/建议类任务被标注了概念设计或方案支持深度，"
                        "且排除完整设计交付，可能被误判成完整设计流程"
                    ),
                    suggestion=(
                        "专项咨询建议改用 PROJECT_DIAGNOSIS / TECHNICAL_PROPOSAL / DECISION_SUPPORT，"
                        "并避免 CONCEPT_DESIGN / SCHEMATIC_SUPPORT"
                    ),
                    recoverable=True,
                )
            )
        if misclassified_new_build:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.NEW_BUILD_MISCLASSIFIED",
                    severity=ValidationSeverity.WARNING,
                    field="task_natures",
                    message=(
                        "任务更像专项咨询/诊断，但 task_natures 含 NEW_BUILD，建议改为 "
                        "CONSULTING / STRATEGY / ASSESSMENT 等"
                    ),
                    recoverable=True,
                )
            )

    def _check_blocking_gaps(
        self,
        gaps: list[KnowledgeGap],
        questions: list[ClarifyingQuestion],
        report: MissionValidationReport,
    ) -> None:
        open_blocking = [
            gap
            for gap in gaps
            if gap.blocking and gap.status == KnowledgeGapStatus.OPEN
        ]
        if not open_blocking:
            return

        question_texts = {q.question.strip() for q in questions if q.question.strip()}
        linked_gap_ids = {
            q.knowledge_gap_id for q in questions if q.knowledge_gap_id is not None
        }

        unmatched: list[KnowledgeGap] = []
        for gap in open_blocking:
            covered = gap.id in linked_gap_ids or any(
                gap.question.strip() and gap.question.strip() in text
                for text in question_texts
            ) or any(
                text and text in gap.question
                for text in question_texts
            )
            if not covered:
                unmatched.append(gap)

        report.blocking_gap_ids = [gap.id for gap in open_blocking]
        if unmatched:
            titles = "；".join(gap.question for gap in unmatched[:3])
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.BLOCKING_GAP_WITHOUT_QUESTION",
                    severity=ValidationSeverity.WARNING,
                    field=None,
                    message=f"存在阻塞性知识缺口但缺少对应澄清问题：{titles}",
                    suggestion="为阻塞缺口补充 clarifying_questions，或降低 blocking 标记",
                    recoverable=True,
                )
            )

    def _check_decisions_and_stakeholders(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if mission.decisions_required and not mission.stakeholders:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.DECISIONS_WITHOUT_STAKEHOLDERS",
                    severity=ValidationSeverity.WARNING,
                    field="decisions_required",
                    fields=("stakeholders",),
                    message="已列出关键决策，但未识别利益相关方",
                    suggestion="补充至少一位决策相关 stakeholder",
                    recoverable=True,
                )
            )

    def _check_confidence_vs_unknowns(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        unknown_count = len(mission.key_unknowns)
        high_confidence = mission.confidence >= 0.75
        high_uncertainty = mission.uncertainty_level in {
            UncertaintyLevel.HIGH,
            UncertaintyLevel.CRITICAL,
        }
        if high_confidence and unknown_count >= 3:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.OVERCONFIDENT",
                    severity=ValidationSeverity.WARNING,
                    field="confidence",
                    fields=("key_unknowns",),
                    message=(
                        f"置信度较高（{mission.confidence:.0%}），"
                        f"但关键未知多达 {unknown_count} 项，可能不一致"
                    ),
                    recoverable=True,
                )
            )
        if high_confidence and high_uncertainty:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.CONFIDENCE_VS_UNCERTAINTY",
                    severity=ValidationSeverity.WARNING,
                    field="confidence",
                    fields=("uncertainty_level",),
                    message="置信度高但不确定性等级偏高，请核对 uncertainty_level / confidence",
                    recoverable=True,
                )
            )

    def _check_confirmed_constraints(
        self,
        mission: ProjectMission,
        facts: list[ProjectFact],
        report: MissionValidationReport,
    ) -> None:
        active = [
            fact for fact in facts if fact.verification_status != VerificationStatus.REJECTED
        ]
        confirmed_facts = [fact for fact in active if fact.is_confirmed]
        for constraint in mission.known_constraints:
            if constraint.verification_status != VerificationStatus.USER_CONFIRMED:
                continue
            if _constraint_supported_by_facts(constraint, confirmed_facts + active):
                continue
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.CONSTRAINT_WITHOUT_EVIDENCE",
                    severity=ValidationSeverity.WARNING,
                    field="known_constraints",
                    message=f"已确认约束「{constraint.name}」缺少事实账本证据支撑",
                    recoverable=True,
                )
            )

    def _check_evaluation_criteria(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if not mission.evaluation_criteria:
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.EMPTY_EVALUATION_CRITERIA",
                    severity=ValidationSeverity.WARNING,
                    field="evaluation_criteria",
                    message="评价标准（evaluation_criteria）为空",
                    suggestion="补充至少 1–2 条可衡量的评价标准，便于后续成果选择",
                    recoverable=True,
                )
            )

    def _check_design_questions(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        weak = [
            item
            for item in mission.design_questions
            if item.strip() and not _looks_like_question(item)
        ]
        if weak:
            sample = "；".join(weak[:2])
            report.add(
                MissionValidationIssue(
                    rule_code="MISSION.WEAK_DESIGN_QUESTION",
                    severity=ValidationSeverity.WARNING,
                    field="design_questions",
                    message=f"设计命题更像陈述而非问题：{sample}",
                    suggestion="设计命题宜写成可比较的问题，例如「如何…？」「是否…？」",
                    recoverable=True,
                )
            )


def _normalize_scope(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    return any(marker in stripped for marker in _QUESTION_MARKERS)


def _constraint_supported_by_facts(
    constraint,
    facts: list[ProjectFact],
) -> bool:
    name = constraint.name.lower()
    value = str(constraint.value).lower()
    for fact in facts:
        label = fact.label.lower()
        key = fact.key.lower()
        fact_value = str(fact.value).lower()
        if key in name or key in value or label in name or label in value:
            return True
        if fact_value and fact_value in value:
            return True
    return bool(constraint.evidence_refs)
