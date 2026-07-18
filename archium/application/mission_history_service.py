"""Revision history for Mission, DeliverablePlan, and Workstream artifacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.mission_snapshots import (
    ArtifactDiffResult,
    deliverable_plan_to_snapshot,
    diff_deliverable_plan_snapshots,
    diff_mission_snapshots,
    diff_workstream_snapshots,
    mission_to_snapshot,
    workstream_to_snapshot,
)
from archium.application.revision_service import RevisionService
from archium.application.slide_diff import change_source_label
from archium.domain.deliverable import DeliverablePlan
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.project_mission import ProjectMission
from archium.domain.revision import EntityRevision
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository


class MissionHistoryService:
    """Mission-specific facade over the unified revision service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)
        self._missions = MissionRepository(session)

    def record_snapshot(
        self,
        mission: ProjectMission,
        change_source: RevisionSource,
        *,
        note: str | None = None,
        actor: str | None = None,
    ) -> EntityRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.MISSION,
            entity_id=mission.id,
            lineage_id=mission.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=mission_to_snapshot(mission),
            note=note,
            actor=actor,
        )

    def archive_before_regeneration(
        self,
        mission: ProjectMission,
        *,
        note: str = "重新生成前归档",
    ) -> EntityRevision:
        return self.record_snapshot(mission, RevisionSource.REGENERATION, note=note)

    def list_revisions(self, mission_id: UUID) -> list[EntityRevision]:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            return []
        return self.list_revisions_by_lineage(mission.lineage_id)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def diff_revisions(self, left_id: UUID, right_id: UUID) -> ArtifactDiffResult:
        left = self._require(left_id)
        right = self._require(right_id)
        return diff_mission_snapshots(
            left.snapshot,
            right.snapshot,
            before_label=self.revision_label(left),
            after_label=self.revision_label(right),
            entity_id=left.entity_id or right.entity_id,
        )

    def diff_with_previous(self, revision_id: UUID) -> ArtifactDiffResult | None:
        revision = self._require(revision_id)
        previous = self._revisions.get_previous_revision(
            revision.lineage_id, revision.revision_number
        )
        if previous is None:
            return None
        return self.diff_revisions(previous.id, revision.id)

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        title = str(revision.snapshot.get("title", "Mission"))
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"

    def _require(self, revision_id: UUID) -> EntityRevision:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            raise WorkflowError(f"Mission revision {revision_id} not found")
        return revision


class DeliverablePlanHistoryService:
    """DeliverablePlan revision facade."""

    def __init__(self, session: Session) -> None:
        self._revisions = RevisionService(session)
        self._missions = MissionRepository(session)

    def record_snapshot(
        self,
        plan: DeliverablePlan,
        change_source: RevisionSource,
        *,
        note: str | None = None,
        actor: str | None = None,
    ) -> EntityRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.DELIVERABLE_PLAN,
            entity_id=plan.id,
            lineage_id=plan.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=deliverable_plan_to_snapshot(plan),
            note=note,
            actor=actor,
        )

    def archive_before_regeneration(
        self,
        plan: DeliverablePlan,
        *,
        note: str = "重新规划前归档",
    ) -> EntityRevision:
        return self.record_snapshot(plan, RevisionSource.REGENERATION, note=note)

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def diff_revisions(self, left_id: UUID, right_id: UUID) -> ArtifactDiffResult:
        left = self._require(left_id)
        right = self._require(right_id)
        return diff_deliverable_plan_snapshots(
            left.snapshot,
            right.snapshot,
            before_label=self.revision_label(left),
            after_label=self.revision_label(right),
            entity_id=left.entity_id or right.entity_id,
        )

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · DeliverablePlan"

    def _require(self, revision_id: UUID) -> EntityRevision:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            raise WorkflowError(f"DeliverablePlan revision {revision_id} not found")
        return revision


class WorkstreamHistoryService:
    """Per-workstream revision facade (lineage on each workstream row)."""

    def __init__(self, session: Session) -> None:
        self._revisions = RevisionService(session)
        self._missions = MissionRepository(session)

    def record_snapshot(
        self,
        workstream: Workstream,
        change_source: RevisionSource,
        *,
        note: str | None = None,
        actor: str | None = None,
    ) -> EntityRevision:
        return self._revisions.record(
            entity_type=RevisionEntityType.WORKSTREAM_PLAN,
            entity_id=workstream.id,
            lineage_id=workstream.lineage_id,
            presentation_id=None,
            change_source=change_source,
            snapshot=workstream_to_snapshot(workstream),
            note=note,
            actor=actor,
        )

    def list_revisions_by_lineage(self, lineage_id: UUID) -> list[EntityRevision]:
        return self._revisions.list_by_lineage(lineage_id)

    def diff_revisions(self, left_id: UUID, right_id: UUID) -> ArtifactDiffResult:
        left = self._require(left_id)
        right = self._require(right_id)
        return diff_workstream_snapshots(
            left.snapshot,
            right.snapshot,
            before_label=self.revision_label(left),
            after_label=self.revision_label(right),
            entity_id=left.entity_id or right.entity_id,
        )

    @staticmethod
    def revision_label(revision: EntityRevision) -> str:
        title = str(revision.snapshot.get("title", "Workstream"))
        source = change_source_label(revision.change_source)
        return f"修订 #{revision.revision_number} · {source} · {title}"

    def _require(self, revision_id: UUID) -> EntityRevision:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            raise WorkflowError(f"Workstream revision {revision_id} not found")
        return revision
