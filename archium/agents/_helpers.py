"""Shared helpers for presentation agents."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents.citations import citation_from_draft, enrich_slide_citations
from archium.application.chunk_models import ProjectContextBundle
from archium.application.knowledge_isolation import (
    filter_generation_facts,
    is_reference_document,
)
from archium.application.presentation_models import PresentationRequest
from archium.config.settings import Settings
from archium.domain.citation import Citation
from archium.domain.document import DocumentChunk
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
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
    return build_project_context_bundle(
        session,
        project_id,
        query=query,
        max_chunks=max_chunks,
        settings=settings,
    ).text


def build_project_context_bundle(
    session: Session,
    project_id: UUID,
    *,
    query: str | None = None,
    max_chunks: int = 24,
    settings: Settings | None = None,
) -> ProjectContextBundle:
    """Build prompt context plus chunk metadata for citation linking."""
    from archium.application.fact_retrieval import (
        match_fact_keys_from_query,
        rank_facts_for_context,
    )
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

    document_names: dict[UUID, str] = {}
    for chunk in chunks:
        if chunk.document_id in document_names:
            continue
        document = documents.get_document(chunk.document_id)
        if document is not None:
            document_names[chunk.document_id] = document.filename

    all_facts = facts_repo.list_by_project(project_id)
    reference_doc_ids = {
        str(doc.id)
        for doc in documents.list_by_project(project_id)
        if _is_reference_document_metadata(doc.metadata)
    }
    active_facts = filter_generation_facts(
        [
            fact
            for fact in all_facts
            if fact.verification_status != VerificationStatus.REJECTED
        ],
        reference_document_ids=reference_doc_ids or None,
    )
    query_keys = match_fact_keys_from_query(query or "")
    ranked_facts = rank_facts_for_context(active_facts, query=query, limit=30)
    max_chars = resolved_settings.chunk_context_max_chars

    lines: list[str] = []
    highlighted_keys: set[str] = set()
    if query_keys and ranked_facts:
        matched = [fact for fact in ranked_facts if fact.key in query_keys]
        if matched:
            lines.append("【与检索相关的项目事实 · 结构化优先】")
            for fact in matched:
                lines.append(_format_fact_line(fact))
                highlighted_keys.add(fact.key)

    if chunks:
        lines.append("【文档片段】")
        for chunk in chunks:
            doc_name = document_names.get(chunk.document_id, "未知文档")
            snippet = chunk.content[:max_chars]
            if chunk.content_type == "asset_caption":
                asset_id = chunk.metadata.get("asset_id")
                drawing_type = chunk.metadata.get("drawing_type", "drawing")
                asset_hint = f"[asset_id={asset_id}]" if asset_id else "[asset]"
                lines.append(
                    f"- {asset_hint} [doc={doc_name}] ({drawing_type}) {snippet}"
                )
                continue
            prefix = f"p.{chunk.page_number}" if chunk.page_number else "p.?"
            title = f" [{chunk.section_title}]" if chunk.section_title else ""
            lines.append(
                f"- [chunk_id={chunk.id}] [doc={doc_name}] ({prefix}){title} {snippet}"
            )

    confirmed_facts = [fact for fact in ranked_facts if fact.is_confirmed]
    pending_facts = [fact for fact in ranked_facts if not fact.is_confirmed]
    ledger_facts = [
        fact
        for fact in confirmed_facts + pending_facts
        if fact.key not in highlighted_keys
    ]
    if ledger_facts:
        lines.append("【项目事实账本 · 已确认优先】")
        for fact in ledger_facts:
            lines.append(_format_fact_line(fact))
    if not lines:
        return ProjectContextBundle(text="暂无项目资料，请基于用户需求保守生成。")

    return ProjectContextBundle(
        text="\n".join(lines),
        chunks=chunks,
        document_names=document_names,
    )


def resolve_design_context_bundle(
    session: Session,
    project_id: UUID,
    *,
    manuscript,
    use_manuscript_pipeline: bool,
    query: str | None = None,
    max_chunks: int = 24,
    settings: Settings | None = None,
) -> ProjectContextBundle:
    """Design-stage context: manuscript when pipeline active, else legacy RAG."""
    if use_manuscript_pipeline and manuscript is not None:
        from archium.application.manuscript_prompt import context_bundle_from_manuscript

        return context_bundle_from_manuscript(manuscript)
    return build_project_context_bundle(
        session,
        project_id,
        query=query,
        max_chunks=max_chunks,
        settings=settings,
    )


def resolve_design_context_text(
    session: Session,
    project_id: UUID,
    *,
    manuscript,
    use_manuscript_pipeline: bool,
    query: str | None = None,
    settings: Settings | None = None,
) -> str:
    return resolve_design_context_bundle(
        session,
        project_id,
        manuscript=manuscript,
        use_manuscript_pipeline=use_manuscript_pipeline,
        query=query,
        settings=settings,
    ).text


def _format_fact_line(fact: ProjectFact) -> str:
    unit_suffix = f" {fact.unit}" if fact.unit else ""
    if fact.is_confirmed:
        status = "已确认"
    elif fact.verification_status == VerificationStatus.INFERRED:
        status = "推测"
    else:
        status = fact.verification_status.value
    source = _fact_source_hint(fact)
    conflict = f" · 冲突组={fact.conflict_group}" if fact.conflict_group else ""
    return (
        f"- [{status}] {fact.label}: {fact.value}{unit_suffix}{source}{conflict} "
        f"(confidence={fact.confidence:.2f})"
    )


def _is_reference_document_metadata(metadata: dict[str, object]) -> bool:
    return is_reference_document(metadata)


def _fact_source_hint(fact: ProjectFact) -> str:
    if not fact.source_citations:
        return ""
    citation = fact.source_citations[0]
    page = f" p.{citation.page_number}" if citation.page_number else ""
    document_name = citation.document_name or "资料"
    return f" · 来源={document_name}{page}"


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


def _citation_from_draft(
    item: CitationDraft,
    session: Session,
    *,
    document_names: dict[UUID, str] | None = None,
    context_chunks: list[DocumentChunk] | None = None,
) -> Citation:
    return citation_from_draft(
        item,
        session,
        document_names=document_names,
        context_chunks=context_chunks,
    )


def _visual_from_draft(item: VisualRequirementDraft) -> VisualRequirement:
    return VisualRequirement(
        type=item.type,
        description=item.description,
        required=item.required,
    )


def slide_from_draft(
    draft: SlideDraft,
    *,
    presentation_id: UUID,
    session: Session,
    document_names: dict[UUID, str] | None = None,
    context_chunks: list[DocumentChunk] | None = None,
    version: int = 1,
) -> SlideSpec:
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
        source_citations=[
            _citation_from_draft(
                citation,
                session,
                document_names=document_names,
                context_chunks=context_chunks,
            )
            for citation in draft.source_citations
        ],
        speaker_notes=draft.speaker_notes,
        version=version,
    )


def slides_from_plan(
    plan: SlidePlanDraft,
    *,
    presentation_id: UUID,
    session: Session,
    context_bundle: ProjectContextBundle | None = None,
    project_id: UUID | None = None,
    settings: Settings | None = None,
    version: int = 1,
) -> list[SlideSpec]:
    names = context_bundle.document_names if context_bundle is not None else None
    chunks = context_bundle.chunks if context_bundle is not None else None
    slides = [
        slide_from_draft(
            slide,
            presentation_id=presentation_id,
            session=session,
            document_names=names,
            context_chunks=chunks,
            version=version,
        )
        for slide in plan.slides
    ]
    if context_bundle is not None and project_id is not None:
        for slide in slides:
            enrich_slide_citations(
                slide,
                session=session,
                project_id=project_id,
                context_bundle=context_bundle,
                settings=settings,
            )
    return slides
