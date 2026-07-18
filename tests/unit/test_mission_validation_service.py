"""Tests for MissionValidationService professional consistency checks."""

from __future__ import annotations

from uuid import uuid4

from archium.application.mission_validation_service import MissionValidationService
from archium.domain.enums import (
    ConstraintSource,
    KnowledgeGapCategory,
    KnowledgeGapStatus,
    Priority,
    QuestionAnswerType,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import (
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)

PROJECT_ID = uuid4()
MISSION_ID = uuid4()


def _mission(**overrides: object) -> ProjectMission:
    defaults: dict = {
        "project_id": PROJECT_ID,
        "title": "某医院专项咨询",
        "task_statement": "对既有医院进行专项诊断并提出改善建议",
        "task_natures": [TaskNature.CONSULTING, TaskNature.ASSESSMENT],
        "requested_service_depths": [
            ServiceDepth.PROJECT_DIAGNOSIS,
            ServiceDepth.DECISION_SUPPORT,
        ],
        "in_scope": ["现状诊断", "改善建议"],
        "out_of_scope": ["施工图设计", "设备选型"],
        "stakeholders": [
            Stakeholder(name="院方", role="业主", concerns=["运营效率"]),
        ],
        "decisions_required": ["是否分期改造"],
        "key_unknowns": ["改造预算上限"],
        "design_questions": ["如何在不中断运营的前提下完成分区改造？"],
        "evaluation_criteria": [
            EvaluationCriterion(name="可实施性", description="是否可分期落地"),
        ],
        "uncertainty_level": UncertaintyLevel.MEDIUM,
        "confidence": 0.55,
    }
    defaults.update(overrides)
    return ProjectMission(**defaults)  # type: ignore[arg-type]


def _gap(*, blocking: bool = True, question: str = "改造预算是多少？") -> KnowledgeGap:
    return KnowledgeGap(
        project_id=PROJECT_ID,
        mission_id=MISSION_ID,
        category=KnowledgeGapCategory.BUDGET,
        question=question,
        why_it_matters="影响分期策略",
        blocking=blocking,
        priority=Priority.HIGH,
        status=KnowledgeGapStatus.OPEN,
    )


def _question(*, gap_id=None, text: str = "改造预算上限是多少？") -> ClarifyingQuestion:
    return ClarifyingQuestion(
        project_id=PROJECT_ID,
        mission_id=MISSION_ID,
        knowledge_gap_id=gap_id,
        question=text,
        why_asked="澄清预算约束",
        answer_type=QuestionAnswerType.TEXT,
        priority=Priority.HIGH,
        blocking=True,
    )


class TestMissionValidationService:
    def setup_method(self) -> None:
        self.service = MissionValidationService()

    def test_healthy_mission_passes(self) -> None:
        report = self.service.validate(_mission())
        assert report.ok
        assert report.errors == []

    def test_empty_task_natures_is_recoverable(self) -> None:
        report = self.service.validate(_mission(task_natures=[]))
        assert not report.ok
        assert report.needs_correction
        assert not report.is_fatal
        assert any("task_natures" in err for err in report.recoverable_errors)
        assert "task_natures" in report.inconsistent_fields
        assert any(
            issue.rule_code == "MISSION.MISSING_TASK_NATURE" for issue in report.issues
        )

    def test_scope_conflict_is_recoverable(self) -> None:
        report = self.service.validate(
            _mission(in_scope=["施工图设计", "诊断"], out_of_scope=["施工图设计"])
        )
        assert not report.ok
        assert report.needs_correction
        assert any("冲突" in err for err in report.recoverable_errors)
        assert "in_scope" in report.inconsistent_fields
        assert "out_of_scope" in report.inconsistent_fields
        assert any(issue.rule_code == "MISSION.SCOPE_CONFLICT" for issue in report.issues)
        assert "issues" in report.to_dict()

    def test_empty_service_depth_warns(self) -> None:
        report = self.service.validate(_mission(requested_service_depths=[]))
        assert report.ok
        assert any("服务深度" in w for w in report.warnings)
        assert report.suggestions

    def test_blocking_gap_without_question_warns(self) -> None:
        gap = _gap()
        report = self.service.validate(
            _mission(),
            knowledge_gaps=[gap],
            clarifying_questions=[],
        )
        assert report.ok
        assert gap.id in report.blocking_gap_ids
        assert any("阻塞" in w for w in report.warnings)

    def test_blocking_gap_linked_by_knowledge_gap_id_ok(self) -> None:
        gap = _gap()
        report = self.service.validate(
            _mission(),
            knowledge_gaps=[gap],
            clarifying_questions=[_question(gap_id=gap.id)],
        )
        assert not any("阻塞" in w for w in report.warnings)
        assert report.blocking_gap_ids == [gap.id]

    def test_decisions_without_stakeholders_warns(self) -> None:
        report = self.service.validate(
            _mission(stakeholders=[], decisions_required=["是否扩建"])
        )
        assert any("利益相关方" in w for w in report.warnings)

    def test_high_confidence_many_unknowns_warns(self) -> None:
        report = self.service.validate(
            _mission(
                confidence=0.9,
                key_unknowns=["a", "b", "c", "d"],
            )
        )
        assert any("置信度" in w for w in report.warnings)
        assert "confidence" in report.inconsistent_fields

    def test_confirmed_constraint_without_fact_warns(self) -> None:
        constraint = MissionConstraint(
            name="建筑面积上限",
            value="12000㎡",
            source=ConstraintSource.USER,
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
        report = self.service.validate(
            _mission(known_constraints=[constraint]),
            facts=[],
        )
        assert any("事实账本" in w for w in report.warnings)

    def test_confirmed_constraint_with_fact_ok(self) -> None:
        constraint = MissionConstraint(
            name="建筑面积上限",
            value="12000㎡",
            source=ConstraintSource.USER,
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
        fact = ProjectFact(
            project_id=PROJECT_ID,
            key="building_area",
            label="建筑面积上限",
            value="12000㎡",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
        report = self.service.validate(
            _mission(known_constraints=[constraint]),
            facts=[fact],
        )
        assert not any("事实账本" in w for w in report.warnings)

    def test_empty_evaluation_criteria_warns(self) -> None:
        report = self.service.validate(_mission(evaluation_criteria=[]))
        assert any("评价标准" in w for w in report.warnings)

    def test_design_question_must_look_like_question(self) -> None:
        report = self.service.validate(
            _mission(design_questions=["采用中庭式布局"])
        )
        assert any("设计命题" in w for w in report.warnings)

    def test_consulting_misclassified_as_full_design_warns(self) -> None:
        report = self.service.validate(
            _mission(
                title="医院专项咨询",
                task_statement="专项诊断与改善建议，不做完整设计",
                task_natures=[TaskNature.CONSULTING, TaskNature.NEW_BUILD],
                requested_service_depths=[
                    ServiceDepth.CONCEPT_DESIGN,
                    ServiceDepth.SCHEMATIC_SUPPORT,
                ],
                out_of_scope=["施工图", "完整设计"],
            )
        )
        assert any("误判" in w or "NEW_BUILD" in w for w in report.warnings)
        assert "task_natures" in report.inconsistent_fields

    def test_shallow_depth_for_new_build_warns(self) -> None:
        report = self.service.validate(
            _mission(
                task_natures=[TaskNature.NEW_BUILD],
                requested_service_depths=[ServiceDepth.TASK_INTERPRETATION],
            )
        )
        assert any("低估" in w for w in report.warnings)

    def test_report_to_dict(self) -> None:
        report = self.service.validate(_mission(task_natures=[]))
        payload = report.to_dict()
        assert payload["ok"] is False
        assert payload["errors"]
        assert "blocking_gap_ids" in payload
