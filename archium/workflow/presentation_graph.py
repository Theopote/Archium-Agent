"""LangGraph definition for the presentation generation workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from archium.application.review_service import slides_are_approved
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


def _route_after_slides(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if state.get("require_slides_review"):
        slides = state.get("slides", [])
        if slides and not slides_are_approved(slides):
            return "pause_for_review"
    return "continue"


def _route_after_pause(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    gate = state.get("review_gate")
    if gate == "brief":
        return "generate_storyline"
    if gate == "storyline":
        return "generate_slides"
    if gate == "slides":
        return "export_json"
    return "finalize"


class PresentationWorkflowGraph:
    """Compiled LangGraph for project load → context → brief → slides → export."""

    def __init__(
        self,
        runtime: PresentationWorkflowRuntime,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._runtime = runtime
        self._nodes = PresentationWorkflowNodes(runtime)
        self._checkpointer = checkpointer
        self._graph = self._build()

    def invoke(
        self,
        state: PresentationWorkflowState | None,
        *,
        thread_id: str,
        resume: bool = False,
    ) -> PresentationWorkflowState:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        graph_input: PresentationWorkflowState | Command = Command(resume=True) if resume else (state or {})
        return cast(PresentationWorkflowState, self._graph.invoke(graph_input, config))

    @staticmethod
    def is_interrupted(state: PresentationWorkflowState | dict[str, object]) -> bool:
        return bool(state.get("__interrupt__"))

    def _build(self) -> CompiledStateGraph:
        builder: StateGraph = StateGraph(PresentationWorkflowState)

        builder.add_node("load_project", self._nodes.load_project)
        builder.add_node("validate_sources", self._nodes.validate_sources)
        builder.add_node("retrieve_context", self._nodes.retrieve_context)
        builder.add_node("extract_facts", self._nodes.extract_facts)
        builder.add_node("validate_facts", self._nodes.validate_facts)
        builder.add_node("generate_brief", self._nodes.generate_brief)
        builder.add_node("generate_storyline", self._nodes.generate_storyline)
        builder.add_node("generate_slides", self._nodes.generate_slides)
        builder.add_node("resolve_citations", self._nodes.resolve_citations)
        builder.add_node("match_assets", self._nodes.match_assets)
        builder.add_node("run_content_review", self._nodes.run_content_review)
        builder.add_node("run_evidence_review", self._nodes.run_evidence_review)
        builder.add_node("run_architectural_review", self._nodes.run_architectural_review)
        builder.add_node("run_layout_review", self._nodes.run_layout_review)
        builder.add_node("repair_slides", self._nodes.repair_slides)
        builder.add_node("review_slides", self._nodes.review_slides)
        builder.add_node("export_json", self._nodes.export_json)
        builder.add_node("export_marp", self._nodes.export_marp)
        builder.add_node("pause_for_review", self._nodes.pause_for_review)
        builder.add_node("finalize", self._nodes.finalize)

        builder.add_edge(START, "load_project")
        builder.add_conditional_edges(
            "load_project",
            _route_on_errors,
            {"continue": "validate_sources", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "validate_sources",
            _route_on_errors,
            {"continue": "retrieve_context", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "retrieve_context",
            _route_on_errors,
            {"continue": "extract_facts", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "extract_facts",
            _route_on_errors,
            {"continue": "validate_facts", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "validate_facts",
            _route_on_errors,
            {"continue": "generate_brief", "finalize": "finalize"},
        )
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
        builder.add_edge("generate_slides", "resolve_citations")
        builder.add_edge("resolve_citations", "match_assets")
        builder.add_edge("match_assets", "run_content_review")
        builder.add_edge("run_content_review", "run_evidence_review")
        builder.add_edge("run_evidence_review", "run_architectural_review")
        builder.add_edge("run_architectural_review", "run_layout_review")
        builder.add_edge("run_layout_review", "repair_slides")
        builder.add_edge("repair_slides", "review_slides")
        builder.add_conditional_edges(
            "review_slides",
            _route_after_slides,
            {"continue": "export_json", "pause_for_review": "pause_for_review", "finalize": "finalize"},
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
        builder.add_conditional_edges(
            "pause_for_review",
            _route_after_pause,
            {
                "generate_storyline": "generate_storyline",
                "generate_slides": "generate_slides",
                "export_json": "export_json",
                "finalize": "finalize",
            },
        )
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)
