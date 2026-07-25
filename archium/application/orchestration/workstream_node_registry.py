"""Map WorkstreamType → handler keys and compile WorkstreamNodeSpec lists."""

from __future__ import annotations

from collections import defaultdict, deque
from uuid import UUID

from archium.domain.enums import WorkstreamStatus, WorkstreamType
from archium.domain.orchestration.models import WorkstreamNodeSpec
from archium.domain.workstream import Workstream, detect_workstream_dependency_cycles
from archium.exceptions import WorkflowError

# Handler keys used by the workstream execution graph.
HANDLER_RESEARCH = "research"
HANDLER_STRATEGY_NOTE = "strategy_note"
HANDLER_PRESENTATION_SIGNAL = "presentation_signal"
HANDLER_SKIP = "skip"

_RESEARCH_TYPES = {
    WorkstreamType.DOCUMENT_REVIEW,
    WorkstreamType.HISTORICAL_RESEARCH,
    WorkstreamType.CASE_STUDY,
    WorkstreamType.USER_RESEARCH,
    WorkstreamType.REGULATION_REVIEW,
}

_STRATEGY_TYPES = {
    WorkstreamType.SITE_ANALYSIS,
    WorkstreamType.PROGRAMMING,
    WorkstreamType.FUNCTIONAL_ANALYSIS,
    WorkstreamType.DESIGN_STRATEGY,
}


def handler_key_for_type(workstream_type: WorkstreamType | str) -> str:
    try:
        typed = (
            workstream_type
            if isinstance(workstream_type, WorkstreamType)
            else WorkstreamType(str(workstream_type))
        )
    except ValueError:
        return HANDLER_SKIP
    if typed in _RESEARCH_TYPES:
        return HANDLER_RESEARCH
    if typed in _STRATEGY_TYPES:
        return HANDLER_STRATEGY_NOTE
    if typed == WorkstreamType.PRESENTATION:
        return HANDLER_PRESENTATION_SIGNAL
    return HANDLER_SKIP


def selected_workstreams(workstreams: list[Workstream]) -> list[Workstream]:
    return [
        ws
        for ws in workstreams
        if ws.selected or ws.status in {WorkstreamStatus.SELECTED, WorkstreamStatus.IN_PROGRESS}
    ]


def topological_workstream_order(workstreams: list[Workstream]) -> list[Workstream]:
    """Return workstreams in dependency order; raise if cycles."""
    cycles = detect_workstream_dependency_cycles(workstreams)
    if cycles:
        raise WorkflowError("工作路径依赖存在环，无法编排执行图")
    by_id = {ws.id: ws for ws in workstreams}
    indegree: dict[UUID, int] = {ws.id: 0 for ws in workstreams}
    edges: dict[UUID, list[UUID]] = defaultdict(list)
    for ws in workstreams:
        for dep in ws.dependencies:
            if dep not in by_id:
                continue
            edges[dep].append(ws.id)
            indegree[ws.id] += 1
    queue = deque([ws_id for ws_id, deg in indegree.items() if deg == 0])
    ordered: list[Workstream] = []
    while queue:
        current = queue.popleft()
        ordered.append(by_id[current])
        for nxt in edges[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(ordered) != len(workstreams):
        raise WorkflowError("工作路径拓扑排序失败")
    return ordered


def compile_workstream_node_specs(
    workstreams: list[Workstream],
    *,
    selected_only: bool = True,
) -> list[WorkstreamNodeSpec]:
    pool = selected_workstreams(workstreams) if selected_only else list(workstreams)
    if not pool:
        return []
    ordered = topological_workstream_order(pool)
    return [
        WorkstreamNodeSpec(
            workstream_id=ws.id,
            workstream_type=ws.workstream_type.value
            if hasattr(ws.workstream_type, "value")
            else str(ws.workstream_type),
            title=ws.title,
            depends_on=list(ws.dependencies),
            handler_key=handler_key_for_type(ws.workstream_type),
        )
        for ws in ordered
    ]
