"""LangGraph definition for the project mission planning workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from archium.workflow.planning_nodes import PlanningWorkflowNodes, PlanningWorkflowRuntime
from archium.workflow.planning_state import PlanningWorkflowState


def _route_on_errors(state: PlanningWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "continue"


def _route_after_clarification(state: PlanningWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "revise_mission"


def _route_after_approval(state: PlanningWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "prepare_presentation_request"


class PlanningWorkflowGraph:
    """Compiled LangGraph for mission → clarification → workstreams → deliverables."""

    def __init__(
        self,
        runtime: PlanningWorkflowRuntime,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._runtime = runtime
        self._nodes = PlanningWorkflowNodes(runtime)
        self._checkpointer = checkpointer
        self._graph = self._build()

    def invoke(
        self,
        state: PlanningWorkflowState | None,
        *,
        thread_id: str,
        resume: bool = False,
    ) -> PlanningWorkflowState:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        graph_input: PlanningWorkflowState | Command = (
            Command(resume=True) if resume else (state or {})
        )
        return cast(PlanningWorkflowState, self._graph.invoke(graph_input, config))

    @staticmethod
    def is_interrupted(state: PlanningWorkflowState | dict[str, object]) -> bool:
        return bool(state.get("__interrupt__"))

    def _build(self) -> CompiledStateGraph:
        builder: StateGraph = StateGraph(PlanningWorkflowState)
        nodes = self._nodes

        builder.add_node("load_project_context", nodes.load_project_context)
        builder.add_node("analyze_task", nodes.analyze_task)
        builder.add_node("validate_mission", nodes.validate_mission)
        builder.add_node("await_user_clarification", nodes.await_user_clarification)
        builder.add_node("revise_mission", nodes.revise_mission)
        builder.add_node("plan_workstreams", nodes.plan_workstreams)
        builder.add_node("plan_deliverables", nodes.plan_deliverables)
        builder.add_node("await_plan_approval", nodes.await_plan_approval)
        builder.add_node("prepare_presentation_request", nodes.prepare_presentation_request)
        builder.add_node("finalize", nodes.finalize)

        builder.add_edge(START, "load_project_context")
        builder.add_conditional_edges(
            "load_project_context",
            _route_on_errors,
            {"continue": "analyze_task", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "analyze_task",
            _route_on_errors,
            {"continue": "validate_mission", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "validate_mission",
            _route_on_errors,
            {"continue": "await_user_clarification", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "await_user_clarification",
            _route_after_clarification,
            {"revise_mission": "revise_mission", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "revise_mission",
            _route_on_errors,
            {"continue": "plan_workstreams", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "plan_workstreams",
            _route_on_errors,
            {"continue": "plan_deliverables", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "plan_deliverables",
            _route_on_errors,
            {"continue": "await_plan_approval", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "await_plan_approval",
            _route_after_approval,
            {
                "prepare_presentation_request": "prepare_presentation_request",
                "finalize": "finalize",
            },
        )
        builder.add_conditional_edges(
            "prepare_presentation_request",
            _route_on_errors,
            {"continue": "finalize", "finalize": "finalize"},
        )
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)
