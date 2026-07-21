"""Per-slide generation context — page-scoped facts, assets, and neighbors."""

from __future__ import annotations

from archium.domain._base import DomainModel
from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.fact import ProjectFact
from archium.domain.presentation_manuscript import ManuscriptFact
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema


class SlideGenerationContext(DomainModel):
    """Bounded context for a single slide generation or repair call."""

    slide_spec: SlideSpec
    section_summary: str = ""
    previous_slide_summary: str | None = None
    next_slide_intent: str | None = None
    verified_facts: list[ManuscriptFact] = []
    project_facts: list[ProjectFact] = []
    relevant_assets: list[Asset] = []
    relevant_citations: list[Citation] = []
    template_schema: ArchitecturalContentSchema | None = None

    def estimated_char_count(self) -> int:
        total = len(self.section_summary)
        if self.previous_slide_summary:
            total += len(self.previous_slide_summary)
        if self.next_slide_intent:
            total += len(self.next_slide_intent)
        total += sum(len(fact.statement) for fact in self.verified_facts)
        total += sum(len(f"{fact.label}: {fact.value}") for fact in self.project_facts)
        total += sum(len(asset.filename) + len(asset.description or "") for asset in self.relevant_assets)
        total += sum(len(cite.quote or cite.document_name) for cite in self.relevant_citations)
        total += len(self.slide_spec.title) + len(self.slide_spec.message)
        return total
