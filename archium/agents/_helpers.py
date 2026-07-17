"""Shared helpers for presentation agents."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings
from archium.domain.citation import Citation
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import DocumentRepository, FactRepository
from archium.infrastructure.llm.presentation_schemas import (
    BriefDraft,
    CitationDraft,
    SlideDraft,
    SlidePlanDraft,
    StorylineDraft,
    VisualRequirementDraft,
)


def build_retrieval_query_from_request(request: PresentationRequest) -> str:
    """Build a semantic search query from presentation intent."""
    parts = [
        request.title,
        request.audience,
        request.purpose,
        request.core_message or "",
        request.user_notes or "",
        *request.required_sections,
        *request.audience_concerns,
    ]
    return " ".join(part.strip() for part in parts if part and part.strip())


def build_retrieval_query_from_brief(brief: PresentationBrief) -> str:
    """Build a semantic search query from an approved brief."""
    parts = [
        brief.title,
        brief.audience,
        brief.purpose,
        brief.core_message,
        *brief.required_sections,
        *brief.audience_concerns,
    ]
    return " ".join(part.strip() for part in parts if part and part.strip())


def build_retrieval_query_from_storyline(brief: PresentationBrief, storyline: Storyline) -> str:
    """Build a semantic search query for slide planning."""
    chapter_messages = " ".join(chapter.key_message for chapter in storyline.chapters)
    return " ".join(
        part.strip()
        for part in (build_retrieval_query_from_brief(brief), storyline.thesis, chapter_messages)
        if part.strip()
    )


def build_project_context(
    session: Session,
    project_id: UUID,
    *,
    query: str | None = None,
    max_chunks: int = 24,
    settings: Settings | None = None,
) -> str:
    """Build compact text context from retrieved chunks and project facts."""
    from archium.application.retrieval_service import create_retrieval_service
    from archium.config.settings import get_settings

    resolved_settings = settings or get_settings()
    documents = DocumentRepository(session)
    facts_repo = FactRepository(session)

    if resolved_settings.retrieval_enabled and query and query.strip():
        retrieval = create_retrieval_service(session, resolved_settings)
        chunks = retrieval.retrieve(project_id, query, top_k=max_chunks)
    else:
        chunks = documents.list_chunks_by_project(project_id)[:max_chunks]

    facts = facts_repo.list_by_project(project_id)[:30]
    max_chars = resolved_settings.chunk_context_max_chars

    lines: list[str] = []
    if chunks:
        lines.append("【文档片段】")
        for chunk in chunks:
            prefix = f"p.{chunk.page_number}" if chunk.page_number else "p.?"
            title = f" [{chunk.section_title}]" if chunk.section_title else ""
            snippet = chunk.content[:max_chars]
            lines.append(f"- ({prefix}){title} {snippet}")
    if facts:
        lines.append("【项目事实】")
        for fact in facts:
            lines.append(f"- {fact.label}: {fact.value} ({fact.verification_status.value})")
    if not lines:
        return "暂无项目资料，请基于用户需求保守生成。"
    return "\n".join(lines)


def build_request_context(request: PresentationRequest) -> str:
    parts = [
        f"标题: {request.title}",
        f"对象: {request.audience}",
        f"目的: {request.purpose}",
        f"时长: {request.duration_minutes} 分钟",
        f"目标页数: {request.target_slide_count}",
        f"核心信息: {request.core_message or '待提炼'}",
        f"类型: {request.presentation_type.value}",
        f"语言: {request.language}",
        f"风格: {request.tone}",
    ]
    if request.required_sections:
        parts.append("必须章节: " + ", ".join(request.required_sections))
    if request.excluded_topics:
        parts.append("排除主题: " + ", ".join(request.excluded_topics))
    if request.decisions_required:
        parts.append("需推动决策: " + ", ".join(request.decisions_required))
    if request.audience_concerns:
        parts.append("对象关切: " + ", ".join(request.audience_concerns))
    if request.user_notes:
        parts.append(f"补充说明: {request.user_notes}")
    return "\n".join(parts)


def to_json(model: object) -> str:
    if hasattr(model, "model_dump"):
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return json.dumps(model, ensure_ascii=False, indent=2)


def sanitize_slide_message(message: str) -> str:
    """Keep slide message to a single concise conclusion."""
    stripped = message.strip()
    if stripped.count("。") <= 2 and stripped.count(".") <= 2:
        return stripped
    for sep in ("。", "."):
        if sep in stripped:
            return stripped.split(sep)[0].strip() + sep
    return stripped[:180]


def brief_from_draft(
    draft: BriefDraft,
    *,
    project_id: UUID,
    presentation_id: UUID,
    version: int = 1,
) -> PresentationBrief:
    return PresentationBrief(
        project_id=project_id,
        presentation_id=presentation_id,
        title=draft.title,
        presentation_type=draft.presentation_type,
        audience=draft.audience,
        purpose=draft.purpose,
        duration_minutes=draft.duration_minutes,
        target_slide_count=draft.target_slide_count,
        core_message=draft.core_message,
        decisions_required=list(draft.decisions_required),
        audience_concerns=list(draft.audience_concerns),
        tone=draft.tone,
        required_sections=list(draft.required_sections),
        excluded_topics=list(draft.excluded_topics),
        language=draft.language,
        version=version,
    )


def storyline_from_draft(draft: StorylineDraft, *, presentation_id: UUID, version: int = 1) -> Storyline:
    chapters = [
        Chapter(
            id=chapter.id,
            title=chapter.title,
            purpose=chapter.purpose,
            key_message=chapter.key_message,
            order=chapter.order,
            estimated_slide_count=chapter.estimated_slide_count,
        )
        for chapter in draft.chapters
    ]
    return Storyline(
        presentation_id=presentation_id,
        thesis=draft.thesis,
        narrative_pattern=draft.narrative_pattern,
        chapters=chapters,
        version=version,
    )


def _citation_from_draft(item: CitationDraft) -> Citation:
    from uuid import uuid4

    return Citation(
        document_id=uuid4(),
        document_name=item.document_name,
        page_number=item.page_number,
        quote=item.quote,
        confidence=item.confidence,
    )


def _visual_from_draft(item: VisualRequirementDraft) -> VisualRequirement:
    return VisualRequirement(
        type=item.type,
        description=item.description,
        required=item.required,
    )


def slide_from_draft(draft: SlideDraft, *, presentation_id: UUID, version: int = 1) -> SlideSpec:
    return SlideSpec(
        presentation_id=presentation_id,
        chapter_id=draft.chapter_id,
        order=draft.order,
        title=draft.title,
        message=sanitize_slide_message(draft.message),
        slide_type=draft.slide_type,
        layout_id=draft.layout_id,
        key_points=list(draft.key_points[:5]),
        visual_requirements=[_visual_from_draft(v) for v in draft.visual_requirements],
        source_citations=[_citation_from_draft(c) for c in draft.source_citations],
        speaker_notes=draft.speaker_notes,
        version=version,
    )


def slides_from_plan(plan: SlidePlanDraft, *, presentation_id: UUID, version: int = 1) -> list[SlideSpec]:
    return [slide_from_draft(slide, presentation_id=presentation_id, version=version) for slide in plan.slides]
