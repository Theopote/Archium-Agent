"""Gather project materials evidence for Context Intelligence assessment."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application._helpers import _format_fact_line
from archium.application.knowledge_gap_detection import detect_knowledge_gaps
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
)


@dataclass(frozen=True)
class ProjectEvidencePack:
    """Lightweight materials signal for KnowledgeState assessment."""

    document_count: int = 0
    document_summaries: str = ""
    fact_lines: str = ""
    confirmed_fact_count: int = 0
    extracted_fact_count: int = 0
    pending_fact_count: int = 0
    conflict_fact_count: int = 0
    chunk_excerpts: str = ""
    gap_lines: str = ""
    blocking_gap_count: int = 0

    @property
    def has_evidence(self) -> bool:
        return (
            self.document_count > 0
            or self.confirmed_fact_count > 0
            or self.extracted_fact_count > 0
            or bool(self.fact_lines.strip())
            or bool(self.chunk_excerpts.strip())
        )


def gather_project_evidence(
    session: Session,
    project_id: UUID,
    *,
    max_documents: int = 12,
    max_fact_lines: int = 14,
    max_chunks: int = 5,
    chunk_chars: int = 160,
    max_gaps: int = 8,
) -> ProjectEvidencePack:
    """Collect filenames, facts, short chunks, and knowledge gaps for CI prompts."""
    documents = DocumentRepository(session).list_by_project(project_id)
    doc_lines = [
        f"- {doc.filename}"
        for doc in documents[:max_documents]
        if getattr(doc, "filename", None)
    ]

    facts = FactRepository(session).list_by_project(project_id)
    fact_lines, confirmed, extracted, pending, conflicts = _format_facts(
        facts, limit=max_fact_lines
    )

    chunks = DocumentRepository(session).list_chunks_by_project(project_id)
    chunk_lines = _format_chunks(chunks, limit=max_chunks, max_chars=chunk_chars)

    gap_report = detect_knowledge_gaps(project_id, facts=facts)
    ordered_gaps = sorted(
        gap_report.gaps,
        key=lambda gap: (0 if gap.blocking else 1, gap.category, gap.description),
    )
    gap_lines = [
        f"- [{'阻断' if gap.blocking else '提示'}] {gap.description}"
        for gap in ordered_gaps[:max_gaps]
    ]
    blocking = sum(1 for gap in gap_report.gaps if gap.blocking)

    return ProjectEvidencePack(
        document_count=len(documents),
        document_summaries="\n".join(doc_lines),
        fact_lines="\n".join(fact_lines),
        confirmed_fact_count=confirmed,
        extracted_fact_count=extracted,
        pending_fact_count=pending,
        conflict_fact_count=conflicts,
        chunk_excerpts="\n".join(chunk_lines),
        gap_lines="\n".join(gap_lines),
        blocking_gap_count=blocking,
    )


def build_verified_constraints_block(
    session: Session,
    project_id: UUID,
    *,
    max_lines: int = 6,
    max_chars: int = 400,
) -> str:
    """Short hard-constraint block for exploration direction prompts."""
    facts = FactRepository(session).list_by_project(project_id)
    preferred = [
        fact
        for fact in facts
        if fact.verification_status != VerificationStatus.REJECTED
        and (
            fact.is_confirmed
            or fact.verification_status
            in {VerificationStatus.EXTRACTED, VerificationStatus.INFERRED}
        )
    ]
    preferred.sort(
        key=lambda fact: (
            0 if fact.is_confirmed else 1,
            0 if fact.verification_status != VerificationStatus.INFERRED else 1,
            fact.key,
        )
    )
    lines: list[str] = []
    total = 0
    for fact in preferred:
        if len(lines) >= max_lines:
            break
        line = _format_fact_line(fact)
        if total + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def _format_facts(
    facts: list[ProjectFact],
    *,
    limit: int,
) -> tuple[list[str], int, int, int, int]:
    active = [
        fact
        for fact in facts
        if fact.verification_status != VerificationStatus.REJECTED
    ]
    confirmed = sum(1 for fact in active if fact.is_confirmed)
    extracted = sum(
        1
        for fact in active
        if fact.verification_status == VerificationStatus.EXTRACTED
        and not fact.is_confirmed
    )
    pending = sum(
        1
        for fact in active
        if not fact.is_confirmed
        and fact.verification_status
        not in {VerificationStatus.CONFLICTED, VerificationStatus.REJECTED}
    )
    conflicts = sum(
        1 for fact in active if fact.verification_status == VerificationStatus.CONFLICTED
    )

    ranked = sorted(
        active,
        key=lambda fact: (
            0 if fact.is_confirmed else 1,
            0 if fact.verification_status == VerificationStatus.CONFLICTED else 1,
            0 if fact.verification_status == VerificationStatus.EXTRACTED else 1,
            fact.key,
        ),
    )
    lines = [_format_fact_line(fact) for fact in ranked[:limit]]
    return lines, confirmed, extracted, pending, conflicts


def _format_chunks(chunks: list, *, limit: int, max_chars: int) -> list[str]:
    lines: list[str] = []
    for chunk in chunks:
        if len(lines) >= limit:
            break
        content = " ".join(str(getattr(chunk, "content", "") or "").split())
        if not content:
            continue
        excerpt = content[:max_chars].rstrip()
        if len(content) > max_chars:
            excerpt += "…"
        page = getattr(chunk, "page_number", None)
        section = getattr(chunk, "section_title", None) or ""
        loc = f"p.{page}" if page else "摘录"
        if section:
            loc = f"{loc}/{section}"
        lines.append(f"- [{loc}] {excerpt}")
    return lines
