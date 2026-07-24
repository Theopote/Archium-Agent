"""Allocate citations and visuals when splitting a slide into two pages."""

from __future__ import annotations

from uuid import UUID

from archium.application.slide_repair_policy import contains_protected_signal
from archium.domain.slide import SlideSpec
from archium.domain.slide_split import citation_key


def allocate_citations(
    original: SlideSpec,
    source: SlideSpec,
    continuation: SlideSpec,
    moved_points: list[str],
) -> tuple[list, list, dict[str, UUID]]:
    if not original.source_citations:
        return list(source.source_citations), list(continuation.source_citations), {}

    moved_text = " ".join(moved_points)
    source_evidence = " ".join(source.key_points)
    source_text = " ".join([source.message, *source.key_points])
    mapping: dict[str, UUID] = {}
    source_citations = []
    continuation_citations = []

    for index, citation in enumerate(original.source_citations):
        key = citation_key(citation.document_id, citation.chunk_id, index)
        quote = citation.quote or ""
        quote_in_moved = bool(quote and quote in moved_text)
        quote_in_source = bool(quote and quote in source_text)
        moved_has_protected = contains_protected_signal(moved_text)
        source_has_protected = contains_protected_signal(source_evidence)

        if quote_in_moved or (moved_has_protected and not source_has_protected and not quote_in_source):
            continuation_citations.append(citation)
            mapping[key] = continuation.id
        elif quote_in_source or source_has_protected:
            source_citations.append(citation)
            mapping[key] = source.id
        elif moved_has_protected:
            continuation_citations.append(citation)
            mapping[key] = continuation.id
        else:
            source_citations.append(citation)
            mapping[key] = source.id

    return source_citations, continuation_citations, mapping


def allocate_visuals(
    original: SlideSpec,
    source: SlideSpec,
    continuation: SlideSpec,
    moved_points: list[str],
) -> tuple[list, list, dict[int, UUID]]:
    if not original.visual_requirements:
        return [], [], {}

    moved_text = " ".join(moved_points)
    mapping: dict[int, UUID] = {}
    visuals = list(original.visual_requirements)

    if len(visuals) == 1:
        if contains_protected_signal(moved_text):
            mapping[0] = continuation.id
            return [], visuals, mapping
        mapping[0] = source.id
        return visuals, [], mapping

    split_at = max(1, len(visuals) // 2)
    if contains_protected_signal(moved_text):
        for index in range(split_at, len(visuals)):
            mapping[index] = continuation.id
        return visuals[:split_at], visuals[split_at:], mapping

    for index, _ in enumerate(visuals):
        mapping[index] = source.id
    return visuals, [], mapping


# Backward-compatible private aliases used by older call sites.
_allocate_citations = allocate_citations
_allocate_visuals = allocate_visuals
