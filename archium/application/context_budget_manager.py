"""Per-stage context char/token budget enforcement."""

from __future__ import annotations

from dataclasses import dataclass

from archium.domain.presentation_manuscript import ManuscriptFact
from archium.domain.slide_generation_context import SlideGenerationContext

_DEFAULT_STAGE_LIMITS: dict[str, int] = {
    "slide_generate": 3500,
    "slide_repair": 2800,
    "template_editing": 3200,
    "semantic_content_plan": 2000,
}


@dataclass(frozen=True)
class StageBudget:
    stage: str
    char_limit: int


class ContextBudgetManager:
    """Trim bounded context blocks so whole-project dumps do not reach LLM calls."""

    def __init__(self, stage_limits: dict[str, int] | None = None) -> None:
        self._limits = dict(_DEFAULT_STAGE_LIMITS)
        if stage_limits:
            self._limits.update(stage_limits)

    def char_limit_for(self, stage: str) -> int:
        return self._limits.get(stage, 3000)

    def trim_text(self, text: str, *, stage: str) -> str:
        limit = self.char_limit_for(stage)
        stripped = text.strip()
        if len(stripped) <= limit:
            return stripped
        return stripped[: limit - 1].rstrip() + "…"

    def trim_prompt_block(self, block: str, *, stage: str) -> str:
        return self.trim_text(block, stage=stage)

    def trim_slide_context(
        self,
        context: SlideGenerationContext,
        *,
        stage: str = "slide_generate",
    ) -> SlideGenerationContext:
        limit = self.char_limit_for(stage)
        if context.estimated_char_count() <= limit:
            return context

        verified = list(context.verified_facts)
        project_facts = list(context.project_facts)
        assets = list(context.relevant_assets)
        citations = list(context.relevant_citations)
        section_summary = context.section_summary
        previous = context.previous_slide_summary
        next_intent = context.next_slide_intent

        def fits() -> bool:
            probe = context.model_copy(
                update={
                    "verified_facts": verified,
                    "project_facts": project_facts,
                    "relevant_assets": assets,
                    "relevant_citations": citations,
                    "section_summary": section_summary,
                    "previous_slide_summary": previous,
                    "next_slide_intent": next_intent,
                }
            )
            return probe.estimated_char_count() <= limit

        while not fits():
            if citations:
                citations.pop()
                continue
            if assets:
                assets.pop()
                continue
            if verified:
                verified.pop()
                continue
            if project_facts:
                project_facts.pop()
                continue
            if next_intent and len(next_intent) > 40:
                next_intent = next_intent[:40] + "…"
                continue
            if previous and len(previous) > 40:
                previous = previous[:40] + "…"
                continue
            if len(section_summary) > 60:
                section_summary = section_summary[:60] + "…"
                continue
            break

        return context.model_copy(
            update={
                "verified_facts": verified,
                "project_facts": project_facts,
                "relevant_assets": assets,
                "relevant_citations": citations,
                "section_summary": section_summary,
                "previous_slide_summary": previous,
                "next_slide_intent": next_intent,
            }
        )

    @staticmethod
    def trim_fact_list(facts: list[ManuscriptFact], *, max_items: int) -> list[ManuscriptFact]:
        return facts[:max(0, max_items)]
