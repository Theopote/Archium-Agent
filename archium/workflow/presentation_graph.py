"""LangGraph definition for the presentation generation workflow."""

from __future__ import annotations

from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from archium.workflow.nodes import PresentationWorkflowNodes
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.state import PresentationWorkflowState


def _route_on_errors(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
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
        builder.add_node("finalize", self._nodes.finalize)

        builder.add_edge(START, "generate_brief")
        builder.add_conditional_edges(
            "generate_brief",
            _route_on_errors,
            {"continue": "generate_storyline", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_storyline",
            _route_on_errors,
            {"continue": "generate_slides", "finalize": "finalize"},
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
        builder.add_edge("finalize", END)

        return builder.compile()
