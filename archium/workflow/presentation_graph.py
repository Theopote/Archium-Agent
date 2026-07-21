"""LangGraph definition for the presentation generation workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from archium.application.review_service import slides_are_approved
from archium.application.slide_repair_service import has_repairable_open_issues
from archium.domain.enums import ApprovalStatus
from archium.domain.presentation_manuscript import ManuscriptStatus, PresentationManuscript
from archium.workflow.nodes import PresentationWorkflowNodes
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.state import PresentationWorkflowState


def _route_on_errors(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    return "continue"


def _route_after_validate_facts(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    request = state.get("request")
    if request is not None and request.use_manuscript_pipeline:
        return "build_manuscript"
    return "generate_brief"


def _coerce_manuscript(state: PresentationWorkflowState) -> PresentationManuscript | None:
    manuscript = state.get("manuscript")
    if manuscript is None or isinstance(manuscript, PresentationManuscript):
        return manuscript
    return PresentationManuscript.model_validate(manuscript)


def _route_after_manuscript(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if state.get("require_manuscript_review"):
        manuscript = _coerce_manuscript(state)
        if manuscript is not None and manuscript.status != ManuscriptStatus.READY:
            return "pause_for_review"
    return "generate_brief"


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


def _route_after_outline(state: PresentationWorkflowState) -> str:
    if state.get("errors"):
        return "finalize"
    if state.get("require_outline_review"):
        outline = state.get("outline")
        if outline is not None and outline.approval_status != ApprovalStatus.APPROVED:
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
    if gate == "manuscript":
        return "generate_brief"
    if gate == "brief":
        return "generate_cultural_narrative"
    if gate == "storyline":
        return "generate_outline"
    if gate == "outline":
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
        builder.add_node("build_manuscript", self._nodes.build_manuscript)
        builder.add_node("generate_brief", self._nodes.generate_brief)
        builder.add_node("generate_cultural_narrative", self._nodes.generate_cultural_narrative)
        builder.add_node("generate_renovation_issue_map", self._nodes.generate_renovation_issue_map)
        builder.add_node("generate_reference_style_profile", self._nodes.generate_reference_style_profile)
        builder.add_node("generate_storyline", self._nodes.generate_storyline)
        builder.add_node("sync_manuscript_from_storyline", self._nodes.sync_manuscript_from_storyline)
        builder.add_node("generate_outline", self._nodes.generate_outline)
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
        builder.add_node("export_presentation_spec", self._nodes.export_presentation_spec)
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
            _route_after_validate_facts,
            {
                "build_manuscript": "build_manuscript",
                "generate_brief": "generate_brief",
                "finalize": "finalize",
            },
        )
        builder.add_conditional_edges(
            "build_manuscript",
            _route_after_manuscript,
            {
                "generate_brief": "generate_brief",
                "pause_for_review": "pause_for_review",
                "finalize": "finalize",
            },
        )
        builder.add_conditional_edges(
            "generate_brief",
            _route_after_brief,
            {
                "continue": "generate_cultural_narrative",
                "pause_for_review": "pause_for_review",
                "finalize": "finalize",
            },
        )
        builder.add_edge("generate_cultural_narrative", "generate_renovation_issue_map")
        builder.add_edge("generate_renovation_issue_map", "generate_reference_style_profile")
        builder.add_edge("generate_reference_style_profile", "generate_storyline")
        builder.add_edge("generate_storyline", "sync_manuscript_from_storyline")
        builder.add_conditional_edges(
            "sync_manuscript_from_storyline",
            _route_after_storyline,
            {"continue": "generate_outline", "pause_for_review": "pause_for_review", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "generate_outline",
            _route_after_outline,
            {"continue": "generate_slides", "pause_for_review": "pause_for_review", "finalize": "finalize"},
        )
        builder.add_edge("generate_slides", "resolve_citations")
        builder.add_edge("resolve_citations", "match_assets")
        builder.add_edge("match_assets", "run_content_review")
        builder.add_edge("run_content_review", "run_evidence_review")
        builder.add_edge("run_evidence_review", "run_architectural_review")
        builder.add_edge("run_architectural_review", "run_layout_review")
        builder.add_conditional_edges(
            "run_layout_review",
            self._route_after_layout_review,
            {"repair": "repair_slides", "validate": "review_slides", "finalize": "finalize"},
        )
        builder.add_edge("repair_slides", "run_content_review")
        builder.add_conditional_edges(
            "review_slides",
            _route_after_slides,
            {"continue": "export_json", "pause_for_review": "pause_for_review", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "export_json",
            _route_on_errors,
            {"continue": "export_presentation_spec", "finalize": "finalize"},
        )
        builder.add_conditional_edges(
            "export_presentation_spec",
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
                "generate_brief": "generate_brief",
                "generate_cultural_narrative": "generate_cultural_narrative",
                "generate_renovation_issue_map": "generate_renovation_issue_map",
                "generate_reference_style_profile": "generate_reference_style_profile",
                "generate_storyline": "generate_storyline",
                "generate_outline": "generate_outline",
                "generate_slides": "generate_slides",
                "export_json": "export_json",
                "finalize": "finalize",
            },
        )
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)

    def _route_after_layout_review(self, state: PresentationWorkflowState) -> str:
        if state.get("errors"):
            return "finalize"
        settings = self._runtime.settings
        repair_round = state.get("repair_round", 0)
        if (
            repair_round < settings.slide_repair_max_rounds
            and has_repairable_open_issues(list(state.get("review_issues", [])), settings)
        ):
            return "repair"
        return "validate"
