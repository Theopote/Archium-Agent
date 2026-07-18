"""Clarification handling: answers, assumptions, gaps, and mission revision."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import to_json
from archium.application.mission_history_service import MissionHistoryService
from archium.application.mission_parser import parse_mission_draft, validate_mission_draft
from archium.application.project_mission_service import (
    MissionGenerationResult,
    ProjectMissionService,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import (
    ApprovalStatus,
    AssumptionStatus,
    ConstraintSource,
    KnowledgeGapStatus,
    QuestionStatus,
    RevisionSource,
    VerificationStatus,
)
from archium.domain.knowledge_gap import (
    AnswerValue,
    Assumption,
    ClarifyingQuestion,
    KnowledgeGap,
)
from archium.domain.project_mission import MissionConstraint, ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.mission_schemas import MissionGenerationDraft
from archium.prompts.knowledge_gaps import (
    CLARIFICATION_REVISION_SYSTEM_PROMPT,
    build_clarification_revision_prompt,
)


@dataclass
class ClarificationReadiness:
    """Whether the mission can proceed to workstream planning."""

    can_continue: bool
    open_blocking_questions: list[ClarifyingQuestion] = field(default_factory=list)
    open_questions: list[ClarifyingQuestion] = field(default_factory=list)
    open_blocking_gaps: list[KnowledgeGap] = field(default_factory=list)
    deferred_count: int = 0
    assumed_count: int = 0
    answered_count: int = 0


@dataclass
class ClarificationActionResult:
    mission: ProjectMission
    question: ClarifyingQuestion | None = None
    gap: KnowledgeGap | None = None
    assumption: Assumption | None = None
    readiness: ClarificationReadiness | None = None


class MissionClarificationService:
    """Handle user answers, assumptions, and clarification-driven mission updates."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        mission_service: ProjectMissionService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._mission_service = mission_service or ProjectMissionService(
            session, llm, settings=self._settings
        )
        self._history = MissionHistoryService(session)

    # ── Clarifying questions ───────────────────────────────────────

    def answer_question(
        self,
        question_id: UUID,
        answer: AnswerValue,
        *,
        apply_to_mission: bool = True,
    ) -> ClarificationActionResult:
        question = self._require_question(question_id)
        if answer is None or (isinstance(answer, str) and not answer.strip()):
            raise WorkflowError("回答内容不能为空")
        if isinstance(answer, list) and not answer:
            raise WorkflowError("回答内容不能为空")

        question.answer_with(answer, source="user")
        saved_question = self._missions.save_clarifying_question(question)
        gap = self._sync_gap_from_question(saved_question, resolution=_format_answer(answer))
        mission = self._require_mission(saved_question.mission_id)
        if apply_to_mission:
            mission = self._apply_answer_to_mission(mission, saved_question, _format_answer(answer))
        return ClarificationActionResult(
            mission=mission,
            question=saved_question,
            gap=gap,
            readiness=self.get_readiness(mission.id),
        )

    def assume_question(
        self,
        question_id: UUID,
        *,
        assumption_text: str | None = None,
        apply_to_mission: bool = True,
    ) -> ClarificationActionResult:
        question = self._require_question(question_id)
        text = (assumption_text or question.suggested_assumption or "").strip()
        if not text:
            raise WorkflowError("该问题没有建议假设，请提供假设内容或直接回答")
        if not question.can_assume and assumption_text is None:
            raise WorkflowError("该问题不允许采用建议假设，请直接回答或暂不确定")

        question.assume(text)
        saved_question = self._missions.save_clarifying_question(question)

        assumption = Assumption(
            project_id=saved_question.project_id,
            mission_id=saved_question.mission_id,
            statement=text,
            reason=f"用户采用建议假设以继续：{saved_question.question}",
            scope_of_use="clarification",
            requires_confirmation=True,
            status=AssumptionStatus.ACCEPTED,
            related_gap_ids=(
                [saved_question.knowledge_gap_id] if saved_question.knowledge_gap_id else []
            ),
        )
        saved_assumption = self._missions.save_assumption(assumption)
        gap = self._sync_gap_from_question(saved_question, resolution=text, assumed=True)

        mission = self._require_mission(saved_question.mission_id)
        if apply_to_mission:
            mission = self._apply_assumption_to_mission(mission, text, saved_question.question)
        return ClarificationActionResult(
            mission=mission,
            question=saved_question,
            gap=gap,
            assumption=saved_assumption,
            readiness=self.get_readiness(mission.id),
        )

    def defer_question(self, question_id: UUID) -> ClarificationActionResult:
        question = self._require_question(question_id)
        if question.blocking:
            raise WorkflowError("阻塞性问题不能暂不确定，请回答或采用假设")
        question.defer()
        saved_question = self._missions.save_clarifying_question(question)
        gap = None
        if saved_question.knowledge_gap_id is not None:
            gap = self._missions.get_knowledge_gap(saved_question.knowledge_gap_id)
            if gap is not None and gap.status == KnowledgeGapStatus.OPEN:
                gap.defer()
                gap = self._missions.save_knowledge_gap(gap)
        mission = self._require_mission(saved_question.mission_id)
        return ClarificationActionResult(
            mission=mission,
            question=saved_question,
            gap=gap,
            readiness=self.get_readiness(mission.id),
        )

    def mark_question_not_applicable(self, question_id: UUID) -> ClarificationActionResult:
        question = self._require_question(question_id)
        question.mark_not_applicable()
        saved_question = self._missions.save_clarifying_question(question)
        gap = None
        if saved_question.knowledge_gap_id is not None:
            gap = self._missions.get_knowledge_gap(saved_question.knowledge_gap_id)
            if gap is not None and gap.status == KnowledgeGapStatus.OPEN:
                gap.status = KnowledgeGapStatus.NOT_APPLICABLE
                gap.touch()
                gap = self._missions.save_knowledge_gap(gap)
        mission = self._require_mission(saved_question.mission_id)
        return ClarificationActionResult(
            mission=mission,
            question=saved_question,
            gap=gap,
            readiness=self.get_readiness(mission.id),
        )

    # ── Assumptions ────────────────────────────────────────────────

    def accept_assumption(self, assumption_id: UUID) -> ClarificationActionResult:
        assumption = self._require_assumption(assumption_id)
        assumption.accept()
        saved = self._missions.save_assumption(assumption)
        for gap_id in saved.related_gap_ids:
            gap = self._missions.get_knowledge_gap(gap_id)
            if gap is not None and gap.status == KnowledgeGapStatus.OPEN:
                gap.mark_assumed(saved.statement)
                self._missions.save_knowledge_gap(gap)
        mission = self._apply_assumption_to_mission(
            self._require_mission(saved.mission_id),
            saved.statement,
            saved.reason,
        )
        return ClarificationActionResult(
            mission=mission,
            assumption=saved,
            readiness=self.get_readiness(mission.id),
        )

    def reject_assumption(self, assumption_id: UUID) -> ClarificationActionResult:
        assumption = self._require_assumption(assumption_id)
        assumption.reject()
        saved = self._missions.save_assumption(assumption)
        mission = self._require_mission(saved.mission_id)
        return ClarificationActionResult(
            mission=mission,
            assumption=saved,
            readiness=self.get_readiness(mission.id),
        )

    # ── Knowledge gaps ─────────────────────────────────────────────

    def answer_gap(self, gap_id: UUID, answer: str) -> ClarificationActionResult:
        gap = self._require_gap(gap_id)
        if not answer.strip():
            raise WorkflowError("回答内容不能为空")
        gap.mark_answered(answer.strip())
        saved_gap = self._missions.save_knowledge_gap(gap)
        mission = self._apply_gap_resolution_to_mission(
            self._require_mission(saved_gap.mission_id),
            saved_gap,
            answer.strip(),
        )
        return ClarificationActionResult(
            mission=mission,
            gap=saved_gap,
            readiness=self.get_readiness(mission.id),
        )

    def assume_gap(self, gap_id: UUID, assumption_text: str) -> ClarificationActionResult:
        gap = self._require_gap(gap_id)
        text = assumption_text.strip()
        if not text:
            raise WorkflowError("假设内容不能为空")
        gap.mark_assumed(text)
        saved_gap = self._missions.save_knowledge_gap(gap)
        assumption = Assumption(
            project_id=saved_gap.project_id,
            mission_id=saved_gap.mission_id,
            statement=text,
            reason=f"针对知识缺口：{saved_gap.question}",
            scope_of_use="knowledge_gap",
            status=AssumptionStatus.ACCEPTED,
            related_gap_ids=[saved_gap.id],
        )
        saved_assumption = self._missions.save_assumption(assumption)
        mission = self._apply_assumption_to_mission(
            self._require_mission(saved_gap.mission_id),
            text,
            saved_gap.question,
        )
        return ClarificationActionResult(
            mission=mission,
            gap=saved_gap,
            assumption=saved_assumption,
            readiness=self.get_readiness(mission.id),
        )

    def defer_gap(self, gap_id: UUID) -> ClarificationActionResult:
        gap = self._require_gap(gap_id)
        if gap.blocking:
            raise WorkflowError("阻塞性知识缺口不能暂不确定，请回答或采用假设")
        gap.defer()
        saved_gap = self._missions.save_knowledge_gap(gap)
        mission = self._require_mission(saved_gap.mission_id)
        return ClarificationActionResult(
            mission=mission,
            gap=saved_gap,
            readiness=self.get_readiness(mission.id),
        )

    # ── Readiness & revision ───────────────────────────────────────

    def get_readiness(self, mission_id: UUID) -> ClarificationReadiness:
        self._require_mission(mission_id)
        questions = self._missions.list_clarifying_questions(mission_id)
        gaps = self._missions.list_knowledge_gaps(mission_id)

        open_questions = [q for q in questions if q.status == QuestionStatus.OPEN]
        open_blocking_questions = [q for q in open_questions if q.blocking]
        open_blocking_gaps = [
            g for g in gaps if g.blocking and g.status == KnowledgeGapStatus.OPEN
        ]

        return ClarificationReadiness(
            can_continue=not open_blocking_questions and not open_blocking_gaps,
            open_blocking_questions=open_blocking_questions,
            open_questions=open_questions,
            open_blocking_gaps=open_blocking_gaps,
            deferred_count=sum(1 for q in questions if q.status == QuestionStatus.DEFERRED)
            + sum(1 for g in gaps if g.status == KnowledgeGapStatus.DEFERRED),
            assumed_count=sum(1 for q in questions if q.status == QuestionStatus.ASSUMED)
            + sum(1 for g in gaps if g.status == KnowledgeGapStatus.ASSUMED),
            answered_count=sum(1 for q in questions if q.status == QuestionStatus.ANSWERED)
            + sum(1 for g in gaps if g.status == KnowledgeGapStatus.ANSWERED),
        )

    def ensure_can_continue(self, mission_id: UUID) -> ClarificationReadiness:
        readiness = self.get_readiness(mission_id)
        if not readiness.can_continue:
            names = [q.question for q in readiness.open_blocking_questions]
            names.extend(g.question for g in readiness.open_blocking_gaps)
            raise WorkflowError(
                "仍有阻塞性澄清项未处理，无法进入工作路径规划：" + "；".join(names[:3])
            )
        return readiness

    def revise_mission_after_clarification(
        self,
        mission_id: UUID,
        *,
        require_ready: bool = True,
    ) -> MissionGenerationResult:
        """Revise the same mission in place using clarification outcomes."""
        if require_ready:
            self.ensure_can_continue(mission_id)

        previous = self._require_mission(mission_id)
        summary = self._build_clarification_summary(mission_id)
        context = self._mission_service._build_context(  # noqa: SLF001
            previous.project_id, previous.task_statement
        )
        fact_summary = self._mission_service._build_fact_summary(previous.project_id)  # noqa: SLF001

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=CLARIFICATION_REVISION_SYSTEM_PROMPT,
                user_prompt=build_clarification_revision_prompt(
                    current_mission_json=to_json(previous),
                    clarification_summary=summary,
                    project_context=context,
                    fact_ledger_summary=fact_summary,
                ),
                temperature=0.3,
                json_mode=True,
            ),
            MissionGenerationDraft,
        )

        fact_ledger = self._mission_service._fact_ledger.get_ledger(previous.project_id)  # noqa: SLF001
        fact_models = [
            entry.fact for entry in fact_ledger.entries if entry.fact is not None
        ] + list(fact_ledger.extra_facts)

        validation = validate_mission_draft(draft, fact_models)
        if not validation.ok:
            raise WorkflowError("; ".join(validation.errors))

        parsed = parse_mission_draft(
            draft,
            project_id=previous.project_id,
            facts=fact_models,
            version=previous.version + 1,
        )
        # Keep identity; update content only. Clarification records stay attached.
        # Revised content requires a fresh explicit approval gate.
        revised = parsed.mission.model_copy(
            update={
                "id": previous.id,
                "lineage_id": previous.lineage_id,
                "logical_key": previous.logical_key,
                "created_at": previous.created_at,
                "approval_status": ApprovalStatus.DRAFT,
            }
        )
        revised.touch()
        saved = self._missions.save_mission(revised)
        self._history.record_snapshot(
            saved,
            RevisionSource.CLARIFICATION,
            note="澄清后修订任务理解",
        )
        return MissionGenerationResult(
            mission=saved,
            knowledge_gaps=self._missions.list_knowledge_gaps(saved.id),
            assumptions=self._missions.list_assumptions(saved.id),
            clarifying_questions=self._missions.list_clarifying_questions(saved.id),
            design_questions=self._missions.list_design_questions(saved.id),
            warnings=list(validation.warnings) + parsed.validation_warnings,
        )

    def _build_clarification_summary(self, mission_id: UUID) -> str:
        lines: list[str] = []
        for question in self._missions.list_clarifying_questions(mission_id):
            if question.status == QuestionStatus.OPEN:
                continue
            answer = _format_answer(question.answer) if question.answer is not None else ""
            lines.append(
                f"- 问题「{question.question}」→ 状态={question.status.value}"
                + (f"；回答/假设={answer}" if answer else "")
            )
        for gap in self._missions.list_knowledge_gaps(mission_id):
            if gap.status == KnowledgeGapStatus.OPEN:
                continue
            lines.append(
                f"- 缺口「{gap.question}」→ 状态={gap.status.value}"
                + (f"；处理={gap.resolution}" if gap.resolution else "")
            )
        for assumption in self._missions.list_assumptions(mission_id):
            lines.append(
                f"- 假设「{assumption.statement}」→ 状态={assumption.status.value}"
            )
        return "\n".join(lines) if lines else "暂无澄清结果"

    def _sync_gap_from_question(
        self,
        question: ClarifyingQuestion,
        *,
        resolution: str,
        assumed: bool = False,
    ) -> KnowledgeGap | None:
        if question.knowledge_gap_id is None:
            return None
        gap = self._missions.get_knowledge_gap(question.knowledge_gap_id)
        if gap is None:
            return None
        if assumed:
            gap.mark_assumed(resolution)
        else:
            gap.mark_answered(resolution)
        return self._missions.save_knowledge_gap(gap)

    def _apply_answer_to_mission(
        self,
        mission: ProjectMission,
        question: ClarifyingQuestion,
        answer: str,
    ) -> ProjectMission:
        unknowns = [item for item in mission.key_unknowns if item not in question.question]
        decisions = list(mission.decisions_required)
        note = f"{question.question} → {answer}"
        if note not in decisions:
            decisions.append(note)
        # Remove matching unknown phrases when answered.
        updated = mission.model_copy(
            update={
                "key_unknowns": unknowns,
                "decisions_required": decisions,
            }
        )
        updated.touch()
        return self._missions.save_mission(updated)

    def _apply_assumption_to_mission(
        self,
        mission: ProjectMission,
        statement: str,
        reason: str,
    ) -> ProjectMission:
        constraints = list(mission.known_constraints)
        if not any(item.value == statement for item in constraints):
            constraints.append(
                MissionConstraint(
                    name=f"假设：{reason[:40]}",
                    value=statement,
                    source=ConstraintSource.ASSUMPTION,
                    verification_status=VerificationStatus.INFERRED,
                    importance="medium",
                )
            )
        updated = mission.model_copy(update={"known_constraints": constraints})
        updated.touch()
        return self._missions.save_mission(updated)

    def _apply_gap_resolution_to_mission(
        self,
        mission: ProjectMission,
        gap: KnowledgeGap,
        answer: str,
    ) -> ProjectMission:
        unknowns = [item for item in mission.key_unknowns if item not in gap.question]
        constraints = list(mission.known_constraints)
        constraints.append(
            MissionConstraint(
                name=gap.question[:80],
                value=answer,
                source=ConstraintSource.USER,
                verification_status=VerificationStatus.USER_CONFIRMED,
                importance="high" if gap.priority.value in {"critical", "high"} else "medium",
            )
        )
        updated = mission.model_copy(
            update={"key_unknowns": unknowns, "known_constraints": constraints}
        )
        updated.touch()
        return self._missions.save_mission(updated)

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        return mission

    def _require_question(self, question_id: UUID) -> ClarifyingQuestion:
        question = self._missions.get_clarifying_question(question_id)
        if question is None:
            raise WorkflowError(f"关键问题 {question_id} 不存在")
        return question

    def _require_assumption(self, assumption_id: UUID) -> Assumption:
        assumption = self._missions.get_assumption(assumption_id)
        if assumption is None:
            raise WorkflowError(f"假设 {assumption_id} 不存在")
        return assumption

    def _require_gap(self, gap_id: UUID) -> KnowledgeGap:
        gap = self._missions.get_knowledge_gap(gap_id)
        if gap is None:
            raise WorkflowError(f"知识缺口 {gap_id} 不存在")
        return gap


def _format_answer(value: AnswerValue) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value)
