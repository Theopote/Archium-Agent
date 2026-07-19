"""Parse and validate workstream planning drafts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar
from uuid import UUID, uuid4

from archium.domain.enums import EffortLevel, Priority, WorkstreamStatus, WorkstreamType
from archium.domain.knowledge_gap import KnowledgeGap
from archium.domain.workstream import Workstream, detect_workstream_dependency_cycles
from archium.infrastructure.llm.workstream_schemas import WorkstreamPlanDraft


@dataclass
class WorkstreamParseResult:
    workstreams: list[Workstream] = field(default_factory=list)
    planning_notes: str = ""
    warnings: list[str] = field(default_factory=list)


def parse_workstream_plan_draft(
    draft: WorkstreamPlanDraft,
    *,
    project_id: UUID,
    mission_id: UUID,
    knowledge_gaps: list[KnowledgeGap],
) -> WorkstreamParseResult:
    """Convert draft workstreams to domain models with index→UUID dependency resolution."""
    warnings: list[str] = []
    placeholders: list[Workstream] = []
    draft_items = list(draft.workstreams)

    # First pass: create workstreams without dependencies.
    for item in draft_items:
        placeholders.append(
            Workstream(
                project_id=project_id,
                mission_id=mission_id,
                lineage_id=uuid4(),
                title=item.title,
                workstream_type=_parse_enum(item.workstream_type, WorkstreamType, WorkstreamType.OTHER),
                objective=item.objective,
                questions=list(item.questions),
                inputs_required=list(item.inputs_required),
                activities=list(item.activities),
                outputs=list(item.outputs),
                priority=_parse_enum(item.priority, Priority, Priority.MEDIUM),
                effort_level=_parse_enum(item.effort_level, EffortLevel, EffortLevel.MEDIUM),
                recommended=item.recommended,
                recommendation_reason=(item.reason or "").strip(),
                selected=item.recommended,
            )
        )

    # Second pass: resolve dependency and blocking-gap indices.
    for index, (item, workstream) in enumerate(zip(draft_items, placeholders, strict=True)):
        deps: list[UUID] = []
        for dep_index in item.dependency_indices:
            if 0 <= dep_index < len(placeholders) and dep_index != index:
                deps.append(placeholders[dep_index].id)
            else:
                warnings.append(f"工作路径「{item.title}」依赖下标 {dep_index} 无效，已忽略")
        workstream.dependencies = deps

        blocking: list[UUID] = []
        for gap_index in item.blocking_gap_indices:
            if 0 <= gap_index < len(knowledge_gaps):
                blocking.append(knowledge_gaps[gap_index].id)
            else:
                warnings.append(
                    f"工作路径「{item.title}」阻塞缺口下标 {gap_index} 无效，已忽略"
                )
        workstream.blocking_gaps = blocking

    cycles = detect_workstream_dependency_cycles(placeholders)
    if cycles:
        # Drop cyclic edges rather than failing the whole plan.
        by_id = {ws.id: ws for ws in placeholders}
        for node_id in cycles:
            ws = by_id.get(node_id)
            if ws is not None:
                ws.dependencies = []
        warnings.append("检测到工作路径依赖环，已清空环上依赖以继续")

    # Auto-select recommended items.
    for workstream in placeholders:
        if workstream.recommended:
            workstream.selected = True
            workstream.status = WorkstreamStatus.SELECTED

    return WorkstreamParseResult(
        workstreams=placeholders,
        planning_notes=draft.planning_notes,
        warnings=warnings,
    )


def validate_workstream_plan_draft(draft: WorkstreamPlanDraft) -> list[str]:
    errors: list[str] = []
    if not draft.workstreams:
        errors.append("工作路径规划不能为空")
    titles = [item.title.strip() for item in draft.workstreams]
    if any(not title for title in titles):
        errors.append("工作路径标题不能为空")
    for item in draft.workstreams:
        if not item.objective.strip():
            errors.append(f"工作路径「{item.title}」缺少目标")
    return errors


_EnumT = TypeVar("_EnumT", bound=Enum)


def _parse_enum(value: str, enum_cls: type[_EnumT], fallback: _EnumT) -> _EnumT:
    try:
        return enum_cls(value)
    except ValueError:
        return fallback
