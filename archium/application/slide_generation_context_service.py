"""Assemble bounded per-slide context from manuscript, outline, and deck state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.asset_matching_service import score_asset_for_requirement
from archium.application.context_budget_manager import ContextBudgetManager
from archium.application.fact_retrieval import rank_facts_for_context
from archium.application.knowledge_isolation import filter_generation_facts
from archium.domain.asset import Asset
from archium.domain.citation import Citation
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Storyline
from archium.domain.presentation_manuscript import (
    ManuscriptFact,
    ManuscriptSection,
    PresentationManuscript,
)
from archium.domain.slide import SlideSpec
from archium.domain.slide_generation_context import SlideGenerationContext
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.infrastructure.database.repositories import AssetRepository, FactRepository


def _tokenize(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ")
    return {part for part in normalized.replace("，", " ").replace("。", " ").split() if len(part) > 1}


def _text_relevance(tokens: set[str], text: str) -> float:
    if not tokens or not text.strip():
        return 0.0
    haystack = _tokenize(text)
    if not haystack:
        return 0.0
    overlap = tokens & haystack
    return len(overlap) / max(len(tokens), 1)


def _slide_query_tokens(slide: SlideSpec) -> set[str]:
    parts = [slide.title, slide.message, *slide.key_points]
    tokens: set[str] = set()
    for part in parts:
        tokens |= _tokenize(part)
    return tokens


def _summarize_slide(slide: SlideSpec) -> str:
    message = slide.message.strip()
    if len(message) <= 120:
        return f"{slide.title} — {message}"
    return f"{slide.title} — {message[:117]}…"


def _section_summary(section: OutlineSection | ManuscriptSection) -> str:
    if isinstance(section, OutlineSection):
        lines = [
            f"章节：{section.title}",
            f"目的：{section.purpose}",
            f"核心信息：{section.key_message}",
        ]
        if section.evidence_requirements:
            lines.append("证据要求：" + "；".join(section.evidence_requirements[:4]))
        return "\n".join(lines)
    lines = [
        f"章节：{section.title}",
        f"目的：{section.purpose}",
        f"主张：{section.argument}",
    ]
    if section.key_points:
        lines.append("要点：" + "；".join(section.key_points[:4]))
    return "\n".join(lines)


class SlideGenerationContextService:
    """Build SlideGenerationContext without dumping the whole project into prompts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._assets = AssetRepository(session)
        self._facts = FactRepository(session)

    def build_for_slide(
        self,
        slide: SlideSpec,
        *,
        all_slides: list[SlideSpec],
        project_id: UUID,
        manuscript: PresentationManuscript | None = None,
        outline: OutlinePlan | None = None,
        storyline: Storyline | None = None,
        template_schema: ArchitecturalContentSchema | None = None,
        max_facts: int = 8,
        max_assets: int = 5,
        max_citations: int = 6,
    ) -> SlideGenerationContext:
        ordered = sorted(all_slides, key=lambda item: (item.chapter_id, item.order))
        index = next((i for i, item in enumerate(ordered) if item.id == slide.id), -1)
        previous_summary = (
            _summarize_slide(ordered[index - 1]) if index > 0 else None
        )
        next_intent = (
            ordered[index + 1].title.strip() if 0 <= index < len(ordered) - 1 else None
        )

        section = self._resolve_section(
            slide.chapter_id,
            manuscript=manuscript,
            outline=outline,
            storyline=storyline,
        )
        section_text = _section_summary(section) if section is not None else ""

        query_tokens = _slide_query_tokens(slide)
        verified_facts = self._select_manuscript_facts(
            slide,
            manuscript=manuscript,
            section=section if isinstance(section, ManuscriptSection) else None,
            query_tokens=query_tokens,
            limit=max_facts,
        )
        project_facts = self._select_project_facts(
            project_id,
            query_tokens=query_tokens,
            limit=max(0, max_facts - len(verified_facts)),
        )
        relevant_assets = self._select_assets(
            slide,
            project_id=project_id,
            query_tokens=query_tokens,
            limit=max_assets,
        )
        relevant_citations = self._select_citations(
            slide,
            manuscript=manuscript,
            section=section if isinstance(section, ManuscriptSection) else None,
            limit=max_citations,
        )

        return ContextBudgetManager().trim_slide_context(
            SlideGenerationContext(
                slide_spec=slide,
                section_summary=section_text,
                previous_slide_summary=previous_summary,
                next_slide_intent=next_intent,
                verified_facts=verified_facts,
                project_facts=project_facts,
                relevant_assets=relevant_assets,
                relevant_citations=relevant_citations,
                template_schema=template_schema,
            ),
            stage="slide_generate",
        )

    def build_for_deck(
        self,
        slides: list[SlideSpec],
        *,
        project_id: UUID,
        manuscript: PresentationManuscript | None = None,
        outline: OutlinePlan | None = None,
        storyline: Storyline | None = None,
        **kwargs: object,
    ) -> list[SlideGenerationContext]:
        return [
            self.build_for_slide(
                slide,
                all_slides=slides,
                project_id=project_id,
                manuscript=manuscript,
                outline=outline,
                storyline=storyline,
                **kwargs,  # type: ignore[arg-type]
            )
            for slide in slides
        ]

    def _resolve_section(
        self,
        chapter_id: str,
        *,
        manuscript: PresentationManuscript | None,
        outline: OutlinePlan | None,
        storyline: Storyline | None,
    ) -> OutlineSection | ManuscriptSection | None:
        if manuscript is not None:
            for section in manuscript.sections:
                if section.id == chapter_id:
                    return section
        if outline is not None:
            for section in outline.sections:
                if section.id == chapter_id:
                    return section
        if storyline is not None:
            for chapter in storyline.chapters:
                if chapter.id == chapter_id:
                    return OutlineSection(
                        id=chapter.id,
                        title=chapter.title,
                        purpose=chapter.purpose,
                        key_message=chapter.key_message,
                        order=chapter.order,
                        estimated_slide_count=chapter.estimated_slide_count,
                    )
        return None

    def _select_manuscript_facts(
        self,
        slide: SlideSpec,
        *,
        manuscript: PresentationManuscript | None,
        section: ManuscriptSection | None,
        query_tokens: set[str],
        limit: int,
    ) -> list[ManuscriptFact]:
        if manuscript is None or limit <= 0:
            return []
        candidates: list[ManuscriptFact] = []
        if section is not None and section.fact_ids:
            for fact_id in section.fact_ids:
                fact = manuscript.fact_by_id(fact_id)
                if fact is not None:
                    candidates.append(fact)
        for fact in manuscript.verified_facts:
            if fact not in candidates:
                candidates.append(fact)

        scored = sorted(
            candidates,
            key=lambda fact: (
                1 if fact.verified else 0,
                _text_relevance(query_tokens, fact.statement),
            ),
            reverse=True,
        )
        return scored[:limit]

    def _select_project_facts(
        self,
        project_id: UUID,
        *,
        query_tokens: set[str],
        limit: int,
    ) -> list[ProjectFact]:
        if limit <= 0:
            return []
        facts = self._facts.list_by_project(project_id)
        active = filter_generation_facts(
            [fact for fact in facts if fact.verification_status != VerificationStatus.REJECTED]
        )
        query = " ".join(sorted(query_tokens))
        ranked = rank_facts_for_context(active, query=query, limit=limit)
        return ranked[:limit]

    def _select_assets(
        self,
        slide: SlideSpec,
        *,
        project_id: UUID,
        query_tokens: set[str],
        limit: int,
    ) -> list[Asset]:
        if limit <= 0:
            return []
        project_assets = self._assets.list_by_project(project_id)
        by_id = {asset.id: asset for asset in project_assets}
        selected: list[Asset] = []
        seen: set[UUID] = set()

        def add(asset: Asset) -> None:
            if asset.id in seen:
                return
            seen.add(asset.id)
            selected.append(asset)

        for requirement in slide.visual_requirements:
            for asset_id in requirement.bound_asset_ids():
                asset = by_id.get(asset_id)
                if asset is not None:
                    add(asset)

        if len(selected) >= limit:
            return selected[:limit]

        scored: list[tuple[Asset, float]] = []
        for requirement in slide.visual_requirements:
            for asset in project_assets:
                score = score_asset_for_requirement(requirement, asset)
                text_bonus = _text_relevance(query_tokens, _asset_search_text(asset))
                scored.append((asset, score + text_bonus * 0.15))
        scored.sort(key=lambda item: item[1], reverse=True)
        for asset, score in scored:
            if score <= 0:
                break
            add(asset)
            if len(selected) >= limit:
                break
        return selected[:limit]

    def _select_citations(
        self,
        slide: SlideSpec,
        *,
        manuscript: PresentationManuscript | None,
        section: ManuscriptSection | None,
        limit: int,
    ) -> list[Citation]:
        citations: list[Citation] = list(slide.source_citations)
        seen = {self._citation_key(cite) for cite in citations}

        if manuscript is not None and section is not None:
            for cite_ref_id in section.citation_ids:
                for ref in manuscript.citations:
                    if ref.id != cite_ref_id:
                        continue
                    key = self._citation_key(ref.citation)
                    if key in seen:
                        continue
                    seen.add(key)
                    citations.append(ref.citation)

        return citations[:limit]

    @staticmethod
    def _citation_key(citation: Citation) -> str:
        return f"{citation.document_id}:{citation.chunk_id}:{citation.page_number}"


def _asset_search_text(asset: Asset) -> str:
    parts = [asset.filename, asset.description or "", *asset.tags]
    return " ".join(part for part in parts if part)
