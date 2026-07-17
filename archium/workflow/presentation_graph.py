"""LangGraph definition for the presentation generation workflow."""

from __future__ import annotations

from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from archium.domain.enums import ApprovalStatus
from archium.workflow.nodes import PresentationWorkflowNodes
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.state import PresentationWorkflowState


def _route_on_errors(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "continue"


def _route_after_brief(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if state.get("require_brief_review"):
        brief = state.get("brief")
        if brief is not None and brief.approval_status != ApprovalStatus.APPROVED:
            return "pause_for_review"
    return "continue"


def _route_after_storyline(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if state.get("require_storyline_review"):
        storyline = state.get("storyline")
        if storyline is not None and storyline.approval_status != ApprovalStatus.APPROVED:
            return "pause_for_review"
    return "continue"


class PresentationWorkflowGraph:
    """Compiled LangGraph for brief → storyline → slides → export."""

    def __init__(self, runtime: PresentationWorkflowRuntime) -> None:
        self._runtime = runtime
        self._nodes = PresentationWorkflowNodes(runtime)
        self._graph = self._build()

    def invoke(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        return cast(PresentationWorkflowState, self._graph.invoke(state))

    def _build(self) -> CompiledStateGraph:
        builder: StateGraph = StateGraph(PresentationWorkflowState)

        builder.add_node("generate_brief", self._nodes.generate_brief)
        builder.add_node("generate_storyline", self._nodes.generate_storyline)
        builder.add_node("generate_slides", self._nodes.generate_slides)
        builder.add_node("export_json", self._nodes.export_json)
        builder.add_node("export_marp", self._nodes.export_marp)
        builder.add_node("pause_for_review", self._nodes.pause_for_review)
        builder.add_node("finalize", self._nodes.finalize)

        builder.add_edge(START, "generate_brief")
        builder.add_conditional_edges(
            "generate_brief",
            _route_after_brief,
            {"continue": "generate_storyline", "pause_for_review": "pause_for_review", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_storyline",
            _route_after_storyline,
            {"continue": "generate_slides", "pause_for_review": "pause_for_review", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_slides",
            _route_on_errors,
            {"continue": "export_json", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "export_json",
            _route_on_errors,
            {"continue": "export_marp", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "export_marp",
            _route_on_errors,
            {"continue": "finalize", "finalize": "finalize"},
        )
        builder.add_edge("pause_for_review", END)
        builder.add_edge("finalize", END)

        return builder.compile()
