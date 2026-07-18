"""Repository layer for project mission and adaptive planning persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import ApprovalStatus
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.exceptions import RepositoryError
from archium.infrastructure.database import mission_mappers
from archium.infrastructure.database.models import (
    ClarifyingQuestionORM,
    DeliverablePlanORM,
    DesignQuestionORM,
    KnowledgeGapORM,
    ProjectAssumptionORM,
    ProjectMissionORM,
    WorkstreamORM,
)


def _handle_error(action: str, exc: Exception) -> None:
    raise RepositoryError(f"Database {action} failed: {exc}") from exc


class MissionRepository:
    """CRUD operations for project missions and planning artifacts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── ProjectMission ───────────────────────────────────────────

    def save_mission(self, mission: ProjectMission) -> ProjectMission:
        try:
            orm = self._session.get(ProjectMissionORM, mission.id)
            if orm is None:
                orm = mission_mappers.project_mission_to_orm(mission)
                self._session.add(orm)
            else:
                mission_mappers.project_mission_to_orm(mission, orm)
            self._session.flush()
            return mission_mappers.project_mission_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save mission", exc)
            raise

    def get_mission(self, mission_id: UUID) -> ProjectMission | None:
        orm = self._session.get(ProjectMissionORM, mission_id)
        return mission_mappers.project_mission_to_domain(orm) if orm else None

    def list_missions_by_project(self, project_id: UUID) -> list[ProjectMission]:
        stmt = (
            select(ProjectMissionORM)
            .where(ProjectMissionORM.project_id == project_id)
            .order_by(ProjectMissionORM.version.desc(), ProjectMissionORM.updated_at.desc())
        )
        return [
            mission_mappers.project_mission_to_domain(row) for row in self._session.scalars(stmt)
        ]

    def get_latest_mission_by_lineage(self, lineage_id: UUID) -> ProjectMission | None:
        stmt = (
            select(ProjectMissionORM)
            .where(ProjectMissionORM.lineage_id == lineage_id)
            .order_by(ProjectMissionORM.version.desc())
            .limit(1)
        )
        orm = self._session.scalar(stmt)
        return mission_mappers.project_mission_to_domain(orm) if orm else None

    # ── KnowledgeGap ─────────────────────────────────────────────

    def save_knowledge_gap(self, gap: KnowledgeGap) -> KnowledgeGap:
        try:
            orm = self._session.get(KnowledgeGapORM, gap.id)
            if orm is None:
                orm = mission_mappers.knowledge_gap_to_orm(gap)
                self._session.add(orm)
            else:
                mission_mappers.knowledge_gap_to_orm(gap, orm)
            self._session.flush()
            return mission_mappers.knowledge_gap_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save knowledge gap", exc)
            raise

    def list_knowledge_gaps(self, mission_id: UUID) -> list[KnowledgeGap]:
        stmt = (
            select(KnowledgeGapORM)
            .where(KnowledgeGapORM.mission_id == mission_id)
            .order_by(KnowledgeGapORM.created_at)
        )
        return [
            mission_mappers.knowledge_gap_to_domain(row) for row in self._session.scalars(stmt)
        ]

    # ── Assumption ─────────────────────────────────────────────────

    def save_assumption(self, assumption: Assumption) -> Assumption:
        try:
            orm = self._session.get(ProjectAssumptionORM, assumption.id)
            if orm is None:
                orm = mission_mappers.assumption_to_orm(assumption)
                self._session.add(orm)
            else:
                mission_mappers.assumption_to_orm(assumption, orm)
            self._session.flush()
            return mission_mappers.assumption_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save assumption", exc)
            raise

    def list_assumptions(self, mission_id: UUID) -> list[Assumption]:
        stmt = (
            select(ProjectAssumptionORM)
            .where(ProjectAssumptionORM.mission_id == mission_id)
            .order_by(ProjectAssumptionORM.created_at)
        )
        return [mission_mappers.assumption_to_domain(row) for row in self._session.scalars(stmt)]

    # ── ClarifyingQuestion ─────────────────────────────────────────

    def save_clarifying_question(self, question: ClarifyingQuestion) -> ClarifyingQuestion:
        try:
            orm = self._session.get(ClarifyingQuestionORM, question.id)
            if orm is None:
                orm = mission_mappers.clarifying_question_to_orm(question)
                self._session.add(orm)
            else:
                mission_mappers.clarifying_question_to_orm(question, orm)
            self._session.flush()
            return mission_mappers.clarifying_question_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save clarifying question", exc)
            raise

    def list_clarifying_questions(self, mission_id: UUID) -> list[ClarifyingQuestion]:
        stmt = (
            select(ClarifyingQuestionORM)
            .where(ClarifyingQuestionORM.mission_id == mission_id)
            .order_by(ClarifyingQuestionORM.created_at)
        )
        return [
            mission_mappers.clarifying_question_to_domain(row)
            for row in self._session.scalars(stmt)
        ]

    # ── DesignQuestion ─────────────────────────────────────────────

    def save_design_question(self, question: DesignQuestion) -> DesignQuestion:
        try:
            orm = self._session.get(DesignQuestionORM, question.id)
            if orm is None:
                orm = mission_mappers.design_question_to_orm(question)
                self._session.add(orm)
            else:
                mission_mappers.design_question_to_orm(question, orm)
            self._session.flush()
            return mission_mappers.design_question_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save design question", exc)
            raise

    def list_design_questions(self, mission_id: UUID) -> list[DesignQuestion]:
        stmt = (
            select(DesignQuestionORM)
            .where(DesignQuestionORM.mission_id == mission_id)
            .order_by(DesignQuestionORM.created_at)
        )
        return [
            mission_mappers.design_question_to_domain(row) for row in self._session.scalars(stmt)
        ]

    # ── Workstream ─────────────────────────────────────────────────

    def save_workstream(self, workstream: Workstream) -> Workstream:
        try:
            orm = self._session.get(WorkstreamORM, workstream.id)
            if orm is None:
                orm = mission_mappers.workstream_to_orm(workstream)
                self._session.add(orm)
            else:
                mission_mappers.workstream_to_orm(workstream, orm)
            self._session.flush()
            return mission_mappers.workstream_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save workstream", exc)
            raise

    def list_workstreams(self, mission_id: UUID) -> list[Workstream]:
        stmt = (
            select(WorkstreamORM)
            .where(WorkstreamORM.mission_id == mission_id)
            .order_by(WorkstreamORM.created_at)
        )
        return [mission_mappers.workstream_to_domain(row) for row in self._session.scalars(stmt)]

    def delete_workstreams_for_mission(self, mission_id: UUID) -> int:
        try:
            stmt = select(WorkstreamORM).where(WorkstreamORM.mission_id == mission_id)
            rows = list(self._session.scalars(stmt))
            for row in rows:
                self._session.delete(row)
            self._session.flush()
            return len(rows)
        except SQLAlchemyError as exc:
            _handle_error("delete workstreams", exc)
            raise

    # ── DeliverablePlan ────────────────────────────────────────────

    def save_deliverable_plan(self, plan: DeliverablePlan) -> DeliverablePlan:
        try:
            orm = self._session.get(DeliverablePlanORM, plan.id)
            if orm is None:
                orm = mission_mappers.deliverable_plan_to_orm(plan)
                self._session.add(orm)
            else:
                mission_mappers.deliverable_plan_to_orm(plan, orm)
            self._session.flush()
            return mission_mappers.deliverable_plan_to_domain(orm)
        except SQLAlchemyError as exc:
            _handle_error("save deliverable plan", exc)
            raise

    def get_deliverable_plan(self, plan_id: UUID) -> DeliverablePlan | None:
        orm = self._session.get(DeliverablePlanORM, plan_id)
        return mission_mappers.deliverable_plan_to_domain(orm) if orm else None

    def list_deliverable_plans(self, mission_id: UUID) -> list[DeliverablePlan]:
        stmt = (
            select(DeliverablePlanORM)
            .where(DeliverablePlanORM.mission_id == mission_id)
            .order_by(DeliverablePlanORM.version.desc())
        )
        return [
            mission_mappers.deliverable_plan_to_domain(row) for row in self._session.scalars(stmt)
        ]

    def get_approved_deliverable_plan(self, mission_id: UUID) -> DeliverablePlan | None:
        stmt = (
            select(DeliverablePlanORM)
            .where(
                DeliverablePlanORM.mission_id == mission_id,
                DeliverablePlanORM.approval_status == ApprovalStatus.APPROVED.value,
            )
            .order_by(DeliverablePlanORM.version.desc())
            .limit(1)
        )
        orm = self._session.scalar(stmt)
        return mission_mappers.deliverable_plan_to_domain(orm) if orm else None
