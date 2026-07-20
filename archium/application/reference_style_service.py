"""Reference style document detection, validation, and prompt formatting."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.knowledge_isolation import document_purpose_from_metadata
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentPurpose
from archium.domain.presentation import PresentationBrief
from archium.domain.reference_style import (
    ReferenceStyleProfile,
    StyleColorCue,
    StyleLayoutCue,
    StyleTypographyCue,
)
from archium.infrastructure.database.repositories import DocumentRepository
from archium.infrastructure.llm.presentation_schemas import ReferenceStyleProfileDraft


def list_reference_style_documents(session: Session, project_id: UUID) -> list[SourceDocument]:
    documents = DocumentRepository(session).list_by_project(project_id)
    return [
        doc
        for doc in documents
        if document_purpose_from_metadata(doc.metadata) == DocumentPurpose.REFERENCE_STYLE
    ]


def has_reference_style_documents(session: Session, project_id: UUID) -> bool:
    return bool(list_reference_style_documents(session, project_id))


def build_reference_style_context(
    session: Session,
    project_id: UUID,
    *,
    max_chunks: int = 20,
) -> tuple[str, list[str]]:
    """Return compact text from reference-style chunks and source document ids."""
    style_docs = list_reference_style_documents(session, project_id)
    if not style_docs:
        return "", []

    style_doc_ids = {doc.id for doc in style_docs}
    doc_names = {doc.id: doc.filename for doc in style_docs}
    chunks: list[DocumentChunk] = []
    for chunk in DocumentRepository(session).list_chunks_by_project(project_id):
        if chunk.document_id in style_doc_ids:
            chunks.append(chunk)
        if len(chunks) >= max_chunks:
            break

    if not chunks:
        pending_lines = [f"- {doc.filename}（已标记为参考风格，待解析内容）" for doc in style_docs[:8]]
        return "\n".join(pending_lines), [str(doc.id) for doc in style_docs]

    lines: list[str] = []
    for chunk in chunks:
        name = doc_names.get(chunk.document_id, "reference")
        excerpt = chunk.content.strip().replace("\n", " ")[:400]
        lines.append(f"- [{name}] {excerpt}")
    return "\n".join(lines), [str(doc.id) for doc in style_docs]


def profile_fallback_from_brief(
    brief: PresentationBrief,
    *,
    project_id: UUID,
    source_document_ids: list[str],
    version: int = 1,
) -> ReferenceStyleProfile:
    return ReferenceStyleProfile(
        project_id=project_id,
        style_name=brief.title or "参考风格提炼",
        source_document_ids=source_document_ids,
        mood_keywords=["专业", "克制"],
        image_treatment="待结合参考文件进一步分析图像处理方式",
        pacing_density="balanced",
        do_rules=["保持信息层级清晰", "图纸与照片分区处理"],
        dont_rules=["不要把参考案例内容写成当前项目事实"],
        adaptation_notes=["仅吸收版式与视觉语气，不复制具体项目内容"],
        unsupported_observations=["参考风格文件内容尚未充分解析"],
        version=version,
    )


def profile_from_draft(
    draft: ReferenceStyleProfileDraft,
    *,
    project_id: UUID,
    source_document_ids: list[str],
    version: int = 1,
) -> ReferenceStyleProfile:
    return ReferenceStyleProfile(
        project_id=project_id,
        style_name=draft.style_name,
        source_document_ids=source_document_ids or list(draft.source_document_ids),
        mood_keywords=list(draft.mood_keywords),
        color_cues=[
            StyleColorCue(
                id=item.id,
                name=item.name,
                description=item.description,
                usage=item.usage,
            )
            for item in draft.color_cues
        ],
        typography_cues=[
            StyleTypographyCue(
                id=item.id,
                role=item.role,
                description=item.description,
            )
            for item in draft.typography_cues
        ],
        layout_cues=[
            StyleLayoutCue(
                id=item.id,
                pattern=item.pattern,
                description=item.description,
            )
            for item in draft.layout_cues
        ],
        image_treatment=draft.image_treatment,
        graphic_elements=list(draft.graphic_elements),
        pacing_density=draft.pacing_density,
        do_rules=list(draft.do_rules),
        dont_rules=list(draft.dont_rules),
        adaptation_notes=list(draft.adaptation_notes),
        unsupported_observations=list(draft.unsupported_observations),
        version=version,
    )


def validate_reference_style_profile(profile: ReferenceStyleProfile) -> list[str]:
    issues: list[str] = []
    if not profile.style_name.strip():
        issues.append("缺少 style_name")
    if not profile.source_document_ids:
        issues.append("未关联参考风格文件")
    if not profile.do_rules and not profile.color_cues and not profile.layout_cues:
        issues.append("尚未提炼可执行的视觉规则")
    return issues


def format_reference_style_for_prompt(profile: ReferenceStyleProfile) -> str:
    payload = {
        "style_name": profile.style_name,
        "mood_keywords": profile.mood_keywords,
        "image_treatment": profile.image_treatment,
        "pacing_density": profile.pacing_density,
        "color_cues": [cue.model_dump(mode="json") for cue in profile.color_cues],
        "typography_cues": [cue.model_dump(mode="json") for cue in profile.typography_cues],
        "layout_cues": [cue.model_dump(mode="json") for cue in profile.layout_cues],
        "graphic_elements": profile.graphic_elements,
        "do_rules": profile.do_rules,
        "dont_rules": profile.dont_rules,
        "adaptation_notes": profile.adaptation_notes,
        "unsupported_observations": profile.unsupported_observations,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
