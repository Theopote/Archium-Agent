"""Human scoring rubric for live Mission golden evaluation (M1–M6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RubricCriterion:
    """One scored dimension of live model quality."""

    id: str
    label: str
    max_score: int
    guidance: str


MISSION_LIVE_RUBRIC: tuple[RubricCriterion, ...] = (
    RubricCriterion(
        id="task_nature",
        label="任务性质判断",
        max_score=15,
        guidance="TaskNature 是否贴合任务（新建/改造/咨询/研究等），是否误用 ProjectType 当模板。",
    ),
    RubricCriterion(
        id="scale_and_depth",
        label="尺度与服务深度",
        max_score=10,
        guidance="intervention_scales / requested_service_depths 是否合理，是否低估或高估服务深度。",
    ),
    RubricCriterion(
        id="fact_fidelity",
        label="事实忠实度",
        max_score=20,
        guidance="是否编造面积/预算/指标；已确认事实是否保留；冲突是否未擅自裁定。",
    ),
    RubricCriterion(
        id="unknown_identification",
        label="关键未知识别",
        max_score=15,
        guidance="key_unknowns / knowledge_gaps 是否抓住真正阻塞点，而非泛泛而谈。",
    ),
    RubricCriterion(
        id="clarifying_value",
        label="澄清问题价值",
        max_score=15,
        guidance="问题是否可行动、数量是否克制（建议≤5），是否堆砌无价值问题。",
    ),
    RubricCriterion(
        id="workstream_quality",
        label="Workstream 合理性",
        max_score=15,
        guidance="工作路径是否匹配任务，而非套固定项目模板章节。",
    ),
    RubricCriterion(
        id="deliverable_quality",
        label="Deliverable 合理性",
        max_score=10,
        guidance="成果类型是否匹配（专项咨询≠完整方案 PPT）；排除项是否落实。",
    ),
)


OBSERVATION_CHECKS: tuple[tuple[str, str], ...] = (
    ("fabricated_metrics", "是否编造面积或其他无依据指标"),
    ("consulting_as_full_design", "是否把专项咨询误判成建筑方案/完整设计"),
    ("low_value_questions", "是否生成太多无价值澄清问题"),
    ("project_type_template", "是否把项目类型当成固定模板"),
    ("scope_overreach", "是否过度扩大任务范围"),
    ("missing_stakeholders", "是否遗漏关键利益相关方"),
)


TOTAL_MAX_SCORE = sum(item.max_score for item in MISSION_LIVE_RUBRIC)


@dataclass
class CriterionScore:
    criterion_id: str
    score: int | None = None
    notes: str = ""


@dataclass
class ObservationNote:
    check_id: str
    observed: bool | None = None
    notes: str = ""


@dataclass
class MissionScorecard:
    """Per-case human scorecard; auto-filled scaffold + optional scores."""

    case_id: str
    case_name: str
    model: str
    run_id: str
    auto_flags: list[str] = field(default_factory=list)
    auto_notes: list[str] = field(default_factory=list)
    criteria: list[CriterionScore] = field(default_factory=list)
    observations: list[ObservationNote] = field(default_factory=list)
    total_score: int | None = None
    pass_threshold: int = 70
    reviewer: str = ""
    review_notes: str = ""

    def ensure_scaffold(self) -> None:
        if not self.criteria:
            self.criteria = [
                CriterionScore(criterion_id=item.id) for item in MISSION_LIVE_RUBRIC
            ]
        if not self.observations:
            self.observations = [
                ObservationNote(check_id=check_id) for check_id, _ in OBSERVATION_CHECKS
            ]

    def compute_total(self) -> int | None:
        scores = [item.score for item in self.criteria if item.score is not None]
        if len(scores) != len(MISSION_LIVE_RUBRIC):
            self.total_score = None
            return None
        self.total_score = sum(scores)
        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        self.ensure_scaffold()
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "model": self.model,
            "run_id": self.run_id,
            "auto_flags": list(self.auto_flags),
            "auto_notes": list(self.auto_notes),
            "rubric": [asdict(item) for item in MISSION_LIVE_RUBRIC],
            "criteria": [asdict(item) for item in self.criteria],
            "observations": [asdict(item) for item in self.observations],
            "observation_labels": {k: v for k, v in OBSERVATION_CHECKS},
            "total_score": self.total_score,
            "total_max": TOTAL_MAX_SCORE,
            "pass_threshold": self.pass_threshold,
            "reviewer": self.reviewer,
            "review_notes": self.review_notes,
        }
