"""Dynamic LangGraph for selected WorkstreamPlan nodes (sequential topo order)."""

from __future__ import annotations

from typing import Any, TypedDict, cast
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from archium.application.orchestration.workstream_handlers import (
    SimpleHandlerRuntime,
    WorkstreamNodeResult,
    run_workstream_handler,
)
from archium.application.orchestration.workstream_node_registry import (
    compile_workstream_node_specs,
)
from archium.domain.orchestration.models import WorkstreamNodeSpec
from archium.domain.workstream import Workstream


class WorkstreamExecutionState(TypedDict, total=False):
    project_id: str
    mission_id: str | None
    node_specs: list[dict[str, Any]]
    results: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]
    presentation_ready: bool
    current_index: int


class WorkstreamExecutionGraph:
    """Compile a linear StateGraph from topo-ordered workstream specs."""

    def __init__(
        self,
        runtime: SimpleHandlerRuntime,
        specs: list[WorkstreamNodeSpec],
        workstreams_by_id: dict[UUID, Workstream],
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._runtime = runtime
        self._specs = list(specs)
        self._workstreams_by_id = workstreams_by_id
        self._checkpointer = checkpointer
        self._compiled = self._build()

    @classmethod
    def from_workstreams(
        cls,
        runtime: SimpleHandlerRuntime,
        workstreams: list[Workstream],
        *,
        checkpointer: BaseCheckpointSaver | None = None,
        selected_only: bool = True,
    ) -> WorkstreamExecutionGraph:
        specs = compile_workstream_node_specs(workstreams, selected_only=selected_only)
        by_id = {ws.id: ws for ws in workstreams}
        return cls(runtime, specs, by_id, checkpointer=checkpointer)

    def _build(self) -> CompiledStateGraph:
        builder: StateGraph = StateGraph(WorkstreamExecutionState)

        def run_all(state: WorkstreamExecutionState) -> WorkstreamExecutionState:
            results: list[dict[str, Any]] = list(state.get("results") or [])
            warnings: list[str] = list(state.get("warnings") or [])
            errors: list[str] = list(state.get("errors") or [])
            presentation_ready = bool(state.get("presentation_ready"))
            for spec in self._specs:
                ws = self._workstreams_by_id.get(spec.workstream_id)
                node_result = run_workstream_handler(
                    self._runtime,
                    spec,
                    workstream_objective=ws.objective if ws else "",
                    workstream_questions=list(ws.questions) if ws else [],
                )
                results.append(_result_to_dict(node_result))
                warnings.extend(node_result.warnings)
                if node_result.status == "failed":
                    errors.append(node_result.summary)
                if (
                    node_result.handler_key == "presentation_signal"
                    and node_result.status == "completed"
                ):
                    presentation_ready = True
            return {
                **state,
                "results": results,
                "warnings": warnings,
                "errors": errors,
                "presentation_ready": presentation_ready,
                "current_index": len(self._specs),
                "node_specs": [s.model_dump(mode="json") for s in self._specs],
            }

        builder.add_node("run_workstreams", run_all)
        builder.add_edge(START, "run_workstreams")
        builder.add_edge("run_workstreams", END)
        if self._checkpointer is not None:
            return cast(CompiledStateGraph, builder.compile(checkpointer=self._checkpointer))
        return cast(CompiledStateGraph, builder.compile())

    def invoke(
        self,
        state: WorkstreamExecutionState,
        *,
        thread_id: str,
    ) -> WorkstreamExecutionState:
        config = {"configurable": {"thread_id": thread_id}}
        result = self._compiled.invoke(state, config=config)
        return cast(WorkstreamExecutionState, result)


def _result_to_dict(result: WorkstreamNodeResult) -> dict[str, Any]:
    return {
        "workstream_id": str(result.workstream_id),
        "handler_key": result.handler_key,
        "status": result.status,
        "summary": result.summary,
        "warnings": list(result.warnings),
        "knowledge_item_ids": list(result.knowledge_item_ids),
    }


def initial_workstream_execution_state(
    *,
    project_id: UUID,
    mission_id: UUID | None,
    specs: list[WorkstreamNodeSpec],
) -> WorkstreamExecutionState:
    return {
        "project_id": str(project_id),
        "mission_id": str(mission_id) if mission_id else None,
        "node_specs": [s.model_dump(mode="json") for s in specs],
        "results": [],
        "warnings": [],
        "errors": [],
        "presentation_ready": False,
        "current_index": 0,
    }
