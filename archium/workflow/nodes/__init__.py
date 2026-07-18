"""LangGraph node implementations for the presentation workflow."""

from __future__ import annotations

from archium.workflow.nodes.export import ExportNodesMixin
from archium.workflow.nodes.generation import GenerationNodesMixin
from archium.workflow.nodes.ingestion import IngestionNodesMixin
from archium.workflow.nodes.review import ReviewNodesMixin


class PresentationWorkflowNodes(
    IngestionNodesMixin,
    GenerationNodesMixin,
    ReviewNodesMixin,
    ExportNodesMixin,
):
    """Node handlers that delegate to the Stage 6 presentation pipeline."""

    pass
