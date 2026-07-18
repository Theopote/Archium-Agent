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


@dataclass
class MissionValidationReport:
    """Result of professional consistency checks on a ProjectMission."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    blocking_gap_ids: list[UUID] = field(default_factory=list)
    inconsistent_fields: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "suggestions": list(self.suggestions),
            "blocking_gap_ids": [str(item) for item in self.blocking_gap_ids],
            "inconsistent_fields": list(self.inconsistent_fields),
            "ok": self.ok,
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
        report.inconsistent_fields = list(dict.fromkeys(report.inconsistent_fields))
        return report

    def _check_required_fields(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if not mission.task_statement.strip():
            report.errors.append("任务陈述为空")
            report.inconsistent_fields.append("task_statement")
        if not mission.task_natures:
            report.errors.append("任务性质（task_natures）不能为空，请至少选择一项")
            report.inconsistent_fields.append("task_natures")
        if not mission.requested_service_depths:
            report.warnings.append("未标注服务深度（requested_service_depths），后续工作路径可能偏泛")
            report.inconsistent_fields.append("requested_service_depths")
            report.suggestions.append("建议补充 PROJECT_DIAGNOSIS / CONCEPT_PLANNING 等服务深度")

    def _check_scope_conflict(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        in_scope = {_normalize_scope(item) for item in mission.in_scope if item.strip()}
        out_scope = {_normalize_scope(item) for item in mission.out_of_scope if item.strip()}
        overlap = sorted(in_scope & out_scope)
        if overlap:
            report.errors.append(
                "工作范围与排除范围冲突：" + "、".join(overlap)
            )
            report.inconsistent_fields.extend(["in_scope", "out_of_scope"])

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
            report.warnings.append(
                "任务性质含新建，但服务深度仅有任务解读，可能低估所需工作深度"
            )
            report.inconsistent_fields.append("requested_service_depths")

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
            report.warnings.append(
                "专项咨询/建议类任务被标注了概念设计或方案支持深度，"
                "且排除完整设计交付，可能被误判成完整设计流程"
            )
            report.inconsistent_fields.extend(["task_natures", "requested_service_depths"])
            report.suggestions.append(
                "专项咨询建议改用 PROJECT_DIAGNOSIS / TECHNICAL_PROPOSAL / DECISION_SUPPORT，"
                "并避免 CONCEPT_DESIGN / SCHEMATIC_SUPPORT"
            )
        if misclassified_new_build:
            report.warnings.append(
                "任务更像专项咨询/诊断，但 task_natures 含 NEW_BUILD，建议改为 "
                "CONSULTING / STRATEGY / ASSESSMENT 等"
            )
            report.inconsistent_fields.append("task_natures")

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
            report.warnings.append(
                f"存在阻塞性知识缺口但缺少对应澄清问题：{titles}"
            )
            report.suggestions.append("为阻塞缺口补充 clarifying_questions，或降低 blocking 标记")

    def _check_decisions_and_stakeholders(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if mission.decisions_required and not mission.stakeholders:
            report.warnings.append("已列出关键决策，但未识别利益相关方")
            report.inconsistent_fields.extend(["decisions_required", "stakeholders"])
            report.suggestions.append("补充至少一位决策相关 stakeholder")

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
            report.warnings.append(
                f"置信度较高（{mission.confidence:.0%}），但关键未知多达 {unknown_count} 项，可能不一致"
            )
            report.inconsistent_fields.extend(["confidence", "key_unknowns"])
        if high_confidence and high_uncertainty:
            report.warnings.append("置信度高但不确定性等级偏高，请核对 uncertainty_level / confidence")
            report.inconsistent_fields.extend(["confidence", "uncertainty_level"])

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
            report.warnings.append(
                f"已确认约束「{constraint.name}」缺少事实账本证据支撑"
            )
            report.inconsistent_fields.append("known_constraints")

    def _check_evaluation_criteria(
        self,
        mission: ProjectMission,
        report: MissionValidationReport,
    ) -> None:
        if not mission.evaluation_criteria:
            report.warnings.append("评价标准（evaluation_criteria）为空")
            report.inconsistent_fields.append("evaluation_criteria")
            report.suggestions.append("补充至少 1–2 条可衡量的评价标准，便于后续成果选择")

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
            report.warnings.append(
                f"设计命题更像陈述而非问题：{sample}"
            )
            report.inconsistent_fields.append("design_questions")
            report.suggestions.append("设计命题宜写成可比较的问题，例如「如何…？」「是否…？」")


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
    if constraint.evidence_refs:
        return True
    return False
