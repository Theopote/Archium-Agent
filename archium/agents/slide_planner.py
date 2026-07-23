"""Generate slide plans from storylines."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import (
    build_retrieval_query_from_storyline,
    resolve_design_context_bundle,
    slide_from_draft,
    slides_from_plan,
    to_json,
)
from archium.application.slide_context_prompt import format_slide_generation_context
from archium.application.slide_generation_context_service import SlideGenerationContextService
from archium.application.slide_history_service import SlideHistoryService
from archium.application.slide_lineage import apply_slide_lineage
from archium.application.slide_plan_slots import SlidePlanSlot, build_slide_plan_slots
from archium.application.visual.visual_grammar_recognition import recognize_page_archetype
from archium.application.visual.visual_grammar_slots import ensure_evidence_slots_on_slide
from archium.config.settings import Settings, get_settings
from archium.domain.deck_delivery import mark_slide_delivery
from archium.domain.enums import RevisionSource, SlideDeliveryStatus, SlideType
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.presentation_schemas import SlideDraft, SlidePlanDraft
from archium.prompts.slide_planning import (
    SINGLE_SLIDE_PLAN_SYSTEM_PROMPT,
    SLIDE_PLAN_SYSTEM_PROMPT,
    build_single_slide_plan_user_prompt,
    build_slide_plan_user_prompt,
)

logger = logging.getLogger(__name__)


def _brief_summary(brief: PresentationBrief) -> str:
    return (
        f"标题：{brief.title}\n"
        f"汇报对象：{brief.audience}\n"
        f"目的：{brief.purpose}\n"
        f"核心信息：{brief.core_message}\n"
        f"目标页数：{brief.target_slide_count}"
    )


def _storyline_summary(storyline: Storyline) -> str:
    lines = [f"论点：{storyline.thesis}", "章节："]
    for chapter in sorted(storyline.chapters, key=lambda item: item.order):
        lines.append(f"- [{chapter.id}] {chapter.title} — {chapter.key_message}")
    return "\n".join(lines)


def _placeholder_slide(
    brief: PresentationBrief,
    slot: SlidePlanSlot,
) -> SlideSpec:
    return SlideSpec(
        presentation_id=brief.presentation_id,
        chapter_id=slot.chapter_id,
        order=slot.order,
        title=slot.section_title,
        message=slot.page_intent,
        slide_type=SlideType.CONTENT,
    )


class SlidePlanner:
    """Generate SlideSpec lists."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)

    def generate(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        outline: OutlinePlan | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        version: int = 1,
        replace_existing: bool = True,
    ) -> list[SlideSpec]:
        if replace_existing:
            existing = self._presentations.list_slides(brief.presentation_id)
            if existing:
                SlideHistoryService(self._session).archive_slides_before_regeneration(existing)
            self._presentations.delete_slides_for_presentation(brief.presentation_id)
        else:
            existing = self._presentations.list_slides(brief.presentation_id)

        if self._settings.slide_per_page_generation:
            slides = self._generate_per_page(
                project_id,
                brief,
                storyline,
                outline=outline,
                manuscript=manuscript,
                use_manuscript_pipeline=use_manuscript_pipeline,
                version=version,
            )
        else:
            slides = self._generate_batch(
                project_id,
                brief,
                storyline,
                outline=outline,
                manuscript=manuscript,
                use_manuscript_pipeline=use_manuscript_pipeline,
                version=version,
            )

        if existing:
            apply_slide_lineage(slides, existing)
        saved: list[SlideSpec] = []
        history = SlideHistoryService(self._session)
        for slide in slides:
            recognition = recognize_page_archetype(slide)
            slide = ensure_evidence_slots_on_slide(
                slide,
                archetype=recognition.archetype,
                recipe=recognition.recipe,
            )
            saved.append(self._presentations.save_slide(slide))
            history.record_snapshot(saved[-1], RevisionSource.GENERATED)
        return saved

    def _generate_batch(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        outline: OutlinePlan | None,
        manuscript: PresentationManuscript | None,
        use_manuscript_pipeline: bool,
        version: int,
    ) -> list[SlideSpec]:
        context_bundle = resolve_design_context_bundle(
            self._session,
            project_id,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            query=build_retrieval_query_from_storyline(brief, storyline),
            settings=self._settings,
        )
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=SLIDE_PLAN_SYSTEM_PROMPT,
                user_prompt=build_slide_plan_user_prompt(
                    project_context=context_bundle.text,
                    brief_json=to_json(brief),
                    storyline_json=to_json(storyline),
                    target_slide_count=brief.target_slide_count,
                    outline_json=to_json(outline) if outline is not None else None,
                ),
                temperature=0.5,
            ),
            SlidePlanDraft,
        )
        return slides_from_plan(
            draft,
            presentation_id=brief.presentation_id,
            session=self._session,
            context_bundle=context_bundle,
            project_id=project_id,
            settings=self._settings,
            version=version,
        )

    def _generate_per_page(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        outline: OutlinePlan | None,
        manuscript: PresentationManuscript | None,
        use_manuscript_pipeline: bool,
        version: int,
    ) -> list[SlideSpec]:
        slots = build_slide_plan_slots(brief, storyline, outline=outline)
        context_service = SlideGenerationContextService(self._session)
        generated: list[SlideSpec] = []
        brief_text = _brief_summary(brief)
        storyline_text = _storyline_summary(storyline)
        citation_chunk_limit = min(8, self._settings.retrieval_top_k)

        for slot in slots:
            slide = self._generate_one_slot(
                project_id,
                brief,
                storyline,
                slot=slot,
                generated_so_far=generated,
                outline=outline,
                manuscript=manuscript,
                use_manuscript_pipeline=use_manuscript_pipeline,
                version=version,
                brief_text=brief_text,
                storyline_text=storyline_text,
                citation_chunk_limit=citation_chunk_limit,
                context_service=context_service,
            )
            generated.append(slide)

        from archium.agents.citations import enrich_slide_citations

        for index, slide in enumerate(generated):
            if slide.delivery_status != SlideDeliveryStatus.READY:
                continue
            slot = slots[index]
            slide_query = " ".join(
                part
                for part in (slot.section_title, slide.title, slide.message)
                if part.strip()
            )
            citation_bundle = resolve_design_context_bundle(
                self._session,
                project_id,
                manuscript=manuscript,
                use_manuscript_pipeline=use_manuscript_pipeline,
                query=slide_query,
                max_chunks=citation_chunk_limit,
                settings=self._settings,
            )
            enrich_slide_citations(
                slide,
                session=self._session,
                project_id=project_id,
                context_bundle=citation_bundle,
                settings=self._settings,
            )
        return generated

    def generate_one(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        order: int,
        outline: OutlinePlan | None = None,
        manuscript: PresentationManuscript | None = None,
        use_manuscript_pipeline: bool = False,
        version: int = 1,
        sibling_slides: list[SlideSpec] | None = None,
    ) -> SlideSpec:
        """Generate / regenerate a single page without aborting the deck."""
        slots = build_slide_plan_slots(brief, storyline, outline=outline)
        try:
            slot = next(item for item in slots if item.order == order)
        except StopIteration as exc:
            from archium.exceptions import WorkflowError

            raise WorkflowError(f"No slide plan slot for order={order}") from exc

        context_service = SlideGenerationContextService(self._session)
        return self._generate_one_slot(
            project_id,
            brief,
            storyline,
            slot=slot,
            generated_so_far=list(sibling_slides or []),
            outline=outline,
            manuscript=manuscript,
            use_manuscript_pipeline=use_manuscript_pipeline,
            version=version,
            brief_text=_brief_summary(brief),
            storyline_text=_storyline_summary(storyline),
            citation_chunk_limit=min(8, self._settings.retrieval_top_k),
            context_service=context_service,
        )

    def _generate_one_slot(
        self,
        project_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        *,
        slot: SlidePlanSlot,
        generated_so_far: list[SlideSpec],
        outline: OutlinePlan | None,
        manuscript: PresentationManuscript | None,
        use_manuscript_pipeline: bool,
        version: int,
        brief_text: str,
        storyline_text: str,
        citation_chunk_limit: int,
        context_service: SlideGenerationContextService,
    ) -> SlideSpec:
        placeholder = _placeholder_slide(brief, slot)
        deck_context = [*generated_so_far, placeholder]
        try:
            slide_context = context_service.build_for_slide(
                placeholder,
                all_slides=deck_context,
                project_id=project_id,
                manuscript=manuscript,
                outline=outline,
                storyline=storyline,
            )
            slide_query = " ".join(
                part
                for part in (
                    slot.section_title,
                    slot.page_intent,
                    brief.core_message,
                    *(slot.slide_intent.required_evidence if slot.slide_intent else ()),
                    *(slot.slide_intent.required_assets if slot.slide_intent else ()),
                )
                if part.strip()
            )
            citation_bundle = resolve_design_context_bundle(
                self._session,
                project_id,
                manuscript=manuscript,
                use_manuscript_pipeline=use_manuscript_pipeline,
                query=slide_query,
                max_chunks=citation_chunk_limit,
                settings=self._settings,
            )
            draft = self._llm.generate_structured(
                LLMRequest(
                    system_prompt=SINGLE_SLIDE_PLAN_SYSTEM_PROMPT,
                    user_prompt=build_single_slide_plan_user_prompt(
                        slot_chapter_id=slot.chapter_id,
                        slot_order=slot.order,
                        deck_position=slot.deck_position,
                        deck_total=slot.deck_total,
                        slide_context=format_slide_generation_context(slide_context),
                        brief_summary=brief_text,
                        storyline_summary=storyline_text,
                        intent_card=slot.intent_card_text or None,
                        asset_bindings=slot.asset_bindings_text or None,
                    ),
                    temperature=0.5,
                ),
                SlideDraft,
            )
            slide = slide_from_draft(
                draft,
                presentation_id=brief.presentation_id,
                session=self._session,
                document_names=citation_bundle.document_names,
                context_chunks=citation_bundle.chunks,
                version=version,
            )
            slide.chapter_id = slot.chapter_id
            slide.order = slot.order
            mark_slide_delivery(slide, SlideDeliveryStatus.READY)
            return slide
        except Exception as exc:
            # Single-page failure must not abort the whole deck.
            logger.exception(
                "Slide generation failed for order=%s chapter=%s; keeping fallback page",
                slot.order,
                slot.chapter_id,
            )
            fallback = _placeholder_slide(brief, slot)
            fallback.version = version
            mark_slide_delivery(
                fallback,
                SlideDeliveryStatus.FALLBACK_USED,
                detail=f"generation failed: {exc}",
            )
            return fallback
