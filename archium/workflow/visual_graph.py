"""LangGraph definition for the visual composition workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from archium.domain.enums import ApprovalStatus
from archium.workflow.visual_nodes import VisualWorkflowNodes, VisualWorkflowRuntime
from archium.workflow.visual_state import VisualWorkflowState


def _route_on_errors(state: VisualWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "continue"


def _route_after_art_direction(state: VisualWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if not state.get("require_art_direction_review", True):
        return "continue"
    art = state.get("art_direction")
    if art is not None and art.approval_status == ApprovalStatus.APPROVED:
        return "continue"
    return "await_approval"


def _route_after_validation(state: VisualWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    reports = state.get("validation_reports", [])
    has_invalid = any(not item.get("valid", False) for item in reports)
    repair_round = int(state.get("repair_round", 0))
    max_rounds = int(state.get("max_repair_rounds", 1))
    if has_invalid and repair_round < max_rounds:
        return "repair"
    return "render"


class VisualWorkflowGraph:
    """Compiled LangGraph for ArtDirection → Layout → Render."""

    def __init__(
        self,
        runtime: VisualWorkflowRuntime,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._runtime = runtime
        self._nodes = VisualWorkflowNodes(runtime)
        self._checkpointer = checkpointer
        self._graph = self._build()

    def invoke(
        self,
        state: VisualWorkflowState | None,
        *,
        thread_id: str,
        resume: bool = False,
    ) -> VisualWorkflowState:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        graph_input: VisualWorkflowState | Command = (
            Command(resume=True) if resume else (state or {})
        )
        return cast(VisualWorkflowState, self._graph.invoke(graph_input, config))

    @staticmethod
    def is_interrupted(state: VisualWorkflowState | dict[str, object]) -> bool:
        return bool(state.get("__interrupt__"))

    def _build(self) -> CompiledStateGraph:
        builder: StateGraph = StateGraph(VisualWorkflowState)
        nodes = self._nodes

        builder.add_node("load_presentation_context", nodes.load_presentation_context)
        builder.add_node("load_or_create_design_system", nodes.load_or_create_design_system)
        builder.add_node("generate_art_direction", nodes.generate_art_direction)
        builder.add_node("await_art_direction_approval", nodes.await_art_direction_approval)
        builder.add_node("generate_visual_intents", nodes.generate_visual_intents)
        builder.add_node("generate_layout_candidates", nodes.generate_layout_candidates)
        builder.add_node("select_layouts", nodes.select_layouts)
        builder.add_node("validate_layouts", nodes.validate_layouts)
        builder.add_node("repair_layouts", nodes.repair_layouts)
        builder.add_node("render_presentation", nodes.render_presentation)
        builder.add_node("finalize", nodes.finalize)

        builder.add_edge(START, "load_presentation_context")
        builder.add_conditional_edges(
            "load_presentation_context",
            _route_on_errors,
            {"continue": "load_or_create_design_system", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "load_or_create_design_system",
            _route_on_errors,
            {"continue": "generate_art_direction", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_art_direction",
            _route_after_art_direction,
            {
                "continue": "generate_visual_intents",
                "await_approval": "await_art_direction_approval",
                "finalize": "finalize",
            },
        )
        builder.add_conditional_edges(
            "await_art_direction_approval",
            _route_on_errors,
            {"continue": "generate_visual_intents", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_visual_intents",
            _route_on_errors,
            {"continue": "generate_layout_candidates", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_layout_candidates",
            _route_on_errors,
            {"continue": "select_layouts", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "select_layouts",
            _route_on_errors,
            {"continue": "validate_layouts", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "validate_layouts",
            _route_after_validation,
            {
                "repair": "repair_layouts",
                "render": "render_presentation",
                "finalize": "finalize",
            },
        )
        builder.add_edge("repair_layouts", "validate_layouts")
        builder.add_conditional_edges(
            "render_presentation",
            _route_on_errors,
            {"continue": "finalize", "finalize": "finalize"},
        )
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)
