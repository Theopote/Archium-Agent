"""Snapshots and field diffs for mission planning artifacts."""

from __future__ import annotations

import difflib
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.deliverable import DeliverablePlan
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream


class ArtifactFieldChange(DomainModel):
    field: str
    label: str
    before: str
    after: str
    unified_diff: str | None = None


class ArtifactDiffResult(DomainModel):
    entity_id: UUID | None = None
    before_label: str
    after_label: str
    changes: list[ArtifactFieldChange] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


_MISSION_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "标题"),
    ("task_statement", "任务陈述"),
    ("current_situation", "当前情况"),
    ("primary_problems", "主要问题"),
    ("desired_changes", "希望产生的改变"),
    ("in_scope", "工作范围"),
    ("out_of_scope", "不包含内容"),
    ("decisions_required", "关键决策"),
    ("design_questions", "设计命题"),
    ("key_unknowns", "关键未知"),
    ("uncertainty_level", "不确定性"),
    ("confidence", "置信度"),
    ("approval_status", "审批状态"),
    ("version", "版本"),
)

_DELIVERABLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("approval_status", "审批状态"),
    ("version", "版本"),
    ("deliverable_titles", "成果列表"),
    ("selected_ids", "已选成果"),
)

_WORKSTREAM_FIELDS: tuple[tuple[str, str], ...] = (
    ("title", "标题"),
    ("objective", "目的"),
    ("recommendation_reason", "推荐理由"),
    ("selected", "是否选中"),
    ("status", "状态"),
    ("version", "版本"),
)


def mission_to_snapshot(mission: ProjectMission) -> dict[str, object]:
    return {
        "id": str(mission.id),
        "lineage_id": str(mission.lineage_id),
        "logical_key": mission.logical_key,
        "project_id": str(mission.project_id),
        "title": mission.title,
        "task_statement": mission.task_statement,
        "current_situation": mission.current_situation,
        "primary_problems": list(mission.primary_problems),
        "desired_changes": list(mission.desired_changes),
        "in_scope": list(mission.in_scope),
        "out_of_scope": list(mission.out_of_scope),
        "decisions_required": list(mission.decisions_required),
        "design_questions": list(mission.design_questions),
        "key_unknowns": list(mission.key_unknowns),
        "uncertainty_level": mission.uncertainty_level.value,
        "confidence": mission.confidence,
        "approval_status": mission.approval_status.value,
        "version": mission.version,
        "task_natures": [item.value for item in mission.task_natures],
    }


def deliverable_plan_to_snapshot(plan: DeliverablePlan) -> dict[str, object]:
    return {
        "id": str(plan.id),
        "lineage_id": str(plan.lineage_id),
        "logical_key": plan.logical_key,
        "mission_id": str(plan.mission_id),
        "project_id": str(plan.project_id),
        "approval_status": plan.approval_status.value,
        "version": plan.version,
        "deliverable_titles": [item.title for item in plan.deliverables],
        "selected_ids": [item.id for item in plan.selected_deliverables()],
    }


def workstream_to_snapshot(workstream: Workstream) -> dict[str, object]:
    return {
        "id": str(workstream.id),
        "lineage_id": str(workstream.lineage_id),
        "mission_id": str(workstream.mission_id),
        "title": workstream.title,
        "objective": workstream.objective,
        "recommendation_reason": workstream.recommendation_reason,
        "selected": workstream.selected,
        "recommended": workstream.recommended,
        "status": workstream.status.value,
        "version": workstream.version,
    }


def diff_mission_snapshots(
    before: dict[str, object],
    after: dict[str, object],
    *,
    before_label: str,
    after_label: str,
    entity_id: UUID | None = None,
) -> ArtifactDiffResult:
    return _diff_tracked(
        before,
        after,
        fields=_MISSION_FIELDS,
        before_label=before_label,
        after_label=after_label,
        entity_id=entity_id,
    )


def diff_deliverable_plan_snapshots(
    before: dict[str, object],
    after: dict[str, object],
    *,
    before_label: str,
    after_label: str,
    entity_id: UUID | None = None,
) -> ArtifactDiffResult:
    return _diff_tracked(
        before,
        after,
        fields=_DELIVERABLE_FIELDS,
        before_label=before_label,
        after_label=after_label,
        entity_id=entity_id,
    )


def diff_workstream_snapshots(
    before: dict[str, object],
    after: dict[str, object],
    *,
    before_label: str,
    after_label: str,
    entity_id: UUID | None = None,
) -> ArtifactDiffResult:
    return _diff_tracked(
        before,
        after,
        fields=_WORKSTREAM_FIELDS,
        before_label=before_label,
        after_label=after_label,
        entity_id=entity_id,
    )


def _diff_tracked(
    before: dict[str, object],
    after: dict[str, object],
    *,
    fields: tuple[tuple[str, str], ...],
    before_label: str,
    after_label: str,
    entity_id: UUID | None,
) -> ArtifactDiffResult:
    changes: list[ArtifactFieldChange] = []
    for field, label in fields:
        before_value = _format_value(before.get(field))
        after_value = _format_value(after.get(field))
        if before_value == after_value:
            continue
        changes.append(
            ArtifactFieldChange(
                field=field,
                label=label,
                before=before_value,
                after=after_value,
                unified_diff=_unified_diff(before_value, after_value),
            )
        )
    return ArtifactDiffResult(
        entity_id=entity_id,
        before_label=before_label,
        after_label=after_label,
        changes=changes,
    )


def _format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _unified_diff(before: str, after: str) -> str | None:
    if before == after:
        return None
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    rendered = "\n".join(lines)
    return rendered or None
