"""Enrich ConceptDirection.reference_case_ids from ArchitectureCase library."""

from __future__ import annotations

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.domain.case_ref import normalize_case_id_list
from archium.domain.concept_direction import ConceptDirection


def enrich_direction_case_refs(
    direction: ConceptDirection,
    *,
    library: ArchitectureCaseLibraryService | None = None,
    limit: int = 2,
) -> ConceptDirection:
    """Keep existing ids; if empty, search library from direction text.

    Ensures selected directions can resolve to ArchitectureCase (KN-009).
    """
    existing = normalize_case_id_list(direction.reference_case_ids)
    lib = library or ArchitectureCaseLibraryService()
    known = {case.id for case in lib.list_cases()}
    existing = [case_id for case_id in existing if case_id in known]
    if existing:
        if existing != list(direction.reference_case_ids):
            return direction.model_copy(update={"reference_case_ids": existing})
        return direction

    query = " ".join(
        part
        for part in (
            direction.title,
            direction.theme,
            direction.summary,
            direction.spatial_strategy,
            " ".join(direction.reference_dna),
        )
        if part and str(part).strip()
    )
    matches = lib.search(query, limit=limit, min_score=0.25)
    case_ids = [match.case.id for match in matches if match.case.id in known]
    if not case_ids:
        return direction if not direction.reference_case_ids else direction.model_copy(
            update={"reference_case_ids": []}
        )
    return direction.model_copy(update={"reference_case_ids": case_ids[:limit]})
