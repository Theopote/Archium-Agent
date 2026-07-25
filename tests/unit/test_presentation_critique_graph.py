"""Presentation graph wires PresentationCritic after layout review."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.presentation_intent_layer import ensure_brief_presentation_intent
from archium.domain.enums import PresentationType, SlideType
from archium.domain.presentation import PresentationBrief
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole
from archium.workflow.nodes.review import ReviewNodesMixin
from archium.workflow.presentation_graph import PresentationWorkflowGraph
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.state import PresentationWorkflowState


def test_presentation_graph_includes_critique_node() -> None:
    runtime = MagicMock(spec=PresentationWorkflowRuntime)
    runtime.session = MagicMock()
    runtime.settings = MagicMock()
    runtime.settings.slide_repair_max_rounds = 0
    graph = PresentationWorkflowGraph(runtime, checkpointer=None)
    nodes = set(graph._graph.get_graph().nodes)  # noqa: SLF001
    assert "run_presentation_critique" in nodes
    assert "run_layout_review" in nodes


def test_run_presentation_critique_soft_records_report() -> None:
    session = MagicMock()
    runtime = MagicMock(spec=PresentationWorkflowRuntime)
    runtime.session = session
    runtime.llm = MagicMock()
    runtime.settings = MagicMock()
    runtime.workflow_runs = MagicMock()

    nodes = ReviewNodesMixin(runtime)
    presentation_id = uuid4()
    brief = ensure_brief_presentation_intent(
        PresentationBrief(
            project_id=uuid4(),
            presentation_id=presentation_id,
            title="院领导汇报",
            presentation_type=PresentationType.CLIENT_REVIEW,
            audience="院领导",
            purpose="立项",
            core_message="连廊改善体验",
        )
    )
    slides = [
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="问题",
            message="流线冲突。",
            slide_type=SlideType.CONTENT,
            slide_role=SlideRole.PROBLEM_ANALYSIS,
        )
    ]
    state: PresentationWorkflowState = {
        "presentation_id": str(presentation_id),
        "project_id": str(brief.project_id),
        "workflow_run_id": str(uuid4()),
        "brief": brief,
        "slides": slides,
        "review_issues": [],
        "errors": [],
    }
    nodes._load_slides_for_export = MagicMock(return_value=slides)  # noqa: SLF001
    nodes._persist_checkpoint = MagicMock()  # noqa: SLF001

    out = nodes.run_presentation_critique(state)
    assert out.get("presentation_critique")
    assert "story_strength" in out["presentation_critique"]
    assert out.get("review_issues")
    assert out["current_step"] == "presentation_critique"
