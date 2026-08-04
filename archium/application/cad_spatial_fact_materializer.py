"""Materialize CAD/BIM text semantics into ProjectFact (Topic 05 Phase M3 / APP-021).

No geometry. Uses STANDARD_FACT_KEYS only (floors / constraints / main_function).
"""

from __future__ import annotations

from uuid import UUID

from archium.application.cad_bim_analysis import CadAssetAnalysis
from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.citation import Citation
from archium.domain.document import SourceDocument
from archium.domain.enums import VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.fact_ledger import STANDARD_FACT_KEY_MAP
from archium.infrastructure.database.repositories import FactRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="cad_spatial_facts")


def materialize_cad_spatial_facts(
    session: SessionLike,
    project_id: UUID,
    document: SourceDocument,
    *,
    analysis: CadAssetAnalysis | None = None,
    metadata: dict[str, object] | None = None,
) -> int:
    """Write EXTRACTED spatial inventory facts from CAD/BIM metadata. Returns created count."""
    session = session_of(session)
    meta = dict(metadata or {})
    if analysis is not None:
        meta = {**analysis.as_metadata(), **meta}
    if not meta.get("cad_bim") and analysis is None:
        return 0

    raw_analysis = meta.get("analysis")
    analysis_blob: dict[str, object] = (
        raw_analysis if isinstance(raw_analysis, dict) else {}
    )
    raw_semantics = analysis_blob.get("ifc_semantics")
    semantics: dict[str, object]
    if isinstance(raw_semantics, dict):
        semantics = raw_semantics
    else:
        # Flat fields from analyze_cad_bim_file
        semantics = {
            "storey_count": analysis_blob.get("storey_count") or meta.get("storey_count"),
            "space_count": analysis_blob.get("space_count") or meta.get("space_count"),
            "space_names": analysis_blob.get("space_names") or [],
            "storey_names": analysis_blob.get("storey_names") or [],
            "building_names": analysis_blob.get("building_names") or [],
            "schema": analysis_blob.get("schema") or meta.get("schema"),
        }

    storey_count = _as_int(semantics.get("storey_count"))
    space_count = _as_int(semantics.get("space_count"))
    space_names = _as_str_list(semantics.get("space_names"))
    storey_names = _as_str_list(semantics.get("storey_names"))
    building_names = _as_str_list(semantics.get("building_names"))
    schema = str(semantics.get("schema") or "").strip()

    if storey_count <= 0 and space_count <= 0 and not space_names and not storey_names:
        return 0

    facts = FactRepository(session)
    created = 0
    quote_bits = [
        f"IFC schema={schema}" if schema else "",
        f"storeys={storey_count}" if storey_count else "",
        f"spaces={space_count}" if space_count else "",
    ]
    quote = "；".join(bit for bit in quote_bits if bit) or "CAD/BIM text semantics"

    if storey_count > 0:
        created += _upsert_extracted(
            facts,
            ProjectFact(
                project_id=project_id,
                key="floors",
                label=STANDARD_FACT_KEY_MAP["floors"].label,
                value=str(storey_count),
                category=STANDARD_FACT_KEY_MAP["floors"].category,
                confidence=0.72,
                verification_status=VerificationStatus.EXTRACTED,
                source_citations=[
                    Citation(
                        document_id=document.id,
                        document_name=document.filename,
                        quote=quote,
                        confidence=0.72,
                    )
                ],
            ),
        )

    constraint_parts: list[str] = []
    if storey_names:
        constraint_parts.append("楼层：" + "、".join(storey_names[:8]))
    if space_names:
        constraint_parts.append(
            f"空间清单（{space_count or len(space_names)}）："
            + "、".join(space_names[:12])
        )
    elif space_count > 0:
        constraint_parts.append(f"IFC 空间实体数：{space_count}")
    if building_names:
        constraint_parts.append("建筑：" + "、".join(building_names[:4]))
    if constraint_parts:
        created += _upsert_extracted(
            facts,
            ProjectFact(
                project_id=project_id,
                key="constraints",
                label=STANDARD_FACT_KEY_MAP["constraints"].label,
                value="；".join(constraint_parts),
                category=STANDARD_FACT_KEY_MAP["constraints"].category,
                confidence=0.65,
                verification_status=VerificationStatus.EXTRACTED,
                source_citations=[
                    Citation(
                        document_id=document.id,
                        document_name=document.filename,
                        quote=quote,
                        confidence=0.65,
                    )
                ],
            ),
        )

    if space_names:
        created += _upsert_extracted(
            facts,
            ProjectFact(
                project_id=project_id,
                key="main_function",
                label=STANDARD_FACT_KEY_MAP["main_function"].label,
                value="、".join(space_names[:6]),
                category=STANDARD_FACT_KEY_MAP["main_function"].category,
                confidence=0.55,
                verification_status=VerificationStatus.EXTRACTED,
                source_citations=[
                    Citation(
                        document_id=document.id,
                        document_name=document.filename,
                        quote="IFC Space Names",
                        confidence=0.55,
                    )
                ],
            ),
        )

    if created:
        logger.info(
            "Materialized %s CAD/BIM spatial fact(s) for project %s from %s",
            created,
            project_id,
            document.filename,
        )
    return created


def merge_cad_analysis_into_document(
    document: SourceDocument,
    analysis: CadAssetAnalysis,
) -> SourceDocument:
    """Merge CadAssetAnalysis metadata onto SourceDocument (in-memory)."""
    meta = dict(document.metadata or {})
    meta.update(analysis.as_metadata())
    meta["cad_analyze_completed"] = True
    document.metadata = meta
    return document


def _upsert_extracted(facts: FactRepository, incoming: ProjectFact) -> int:
    """Create if missing; skip when confirmed or same value. Returns 1 if created."""
    existing = facts.get_by_project_key(incoming.project_id, incoming.key)
    if existing is None:
        facts.create(incoming)
        return 1
    if existing.is_confirmed:
        return 0
    # Soft refresh unconfirmed EXTRACTED values from CAD when empty-ish or identical source
    if str(existing.value or "").strip() == str(incoming.value or "").strip():
        return 0
    if existing.verification_status == VerificationStatus.EXTRACTED and not existing.is_confirmed:
        # Prefer richer CAD inventory for constraints / main_function; floors keep first
        if incoming.key == "floors":
            return 0
        existing.value = incoming.value
        existing.confidence = max(existing.confidence, incoming.confidence)
        if incoming.source_citations:
            existing.source_citations = list(existing.source_citations) + list(
                incoming.source_citations
            )
        facts.update(existing)
        return 0
    return 0


def _as_int(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
