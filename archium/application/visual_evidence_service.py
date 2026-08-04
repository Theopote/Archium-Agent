"""Build ArchitecturalAsset packs for Context / Research evidence channels."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.application.knowledge_isolation import document_purpose_from_metadata
from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.architectural_asset import (
    ArchitecturalAsset,
    architectural_asset_from_parts,
    input_source_lines_from_assets,
)
from archium.domain.document import SourceDocument
from archium.domain.enums import DocumentPurpose
from archium.infrastructure.database.repositories import AssetRepository, DocumentRepository


@dataclass(frozen=True)
class VisualEvidencePack:
    assets: tuple[ArchitecturalAsset, ...] = ()

    @property
    def site_photo_count(self) -> int:
        return sum(1 for a in self.assets if a.role.value == "site_photo")

    @property
    def drawing_count(self) -> int:
        return sum(1 for a in self.assets if a.role.value == "drawing")

    @property
    def diagram_count(self) -> int:
        return sum(1 for a in self.assets if a.role.value == "diagram")

    @property
    def reference_count(self) -> int:
        return sum(1 for a in self.assets if a.role.value == "reference")

    @property
    def cad_bim_count(self) -> int:
        return sum(1 for a in self.assets if a.role.value == "cad_bim")

    def input_source_lines(self) -> list[str]:
        return input_source_lines_from_assets(list(self.assets))

    def to_prompt_block(self, *, max_lines: int = 12) -> str:
        lines = [item.to_prompt_line() for item in self.assets[:max_lines]]
        return "\n".join(lines)


def build_visual_evidence_pack(
    session: SessionLike,
    project_id: UUID,
) -> VisualEvidencePack:
    """List project assets + CAD/BIM documents as ArchitecturalAsset facades (no LLM)."""
    session = session_of(session)
    from archium.domain.architectural_asset import architectural_asset_from_document

    documents = DocumentRepository(session).list_by_project(project_id)
    purpose_by_doc: dict[UUID, DocumentPurpose] = {
        doc.id: document_purpose_from_metadata(doc.metadata or {}) for doc in documents
    }
    assets = AssetRepository(session).list_by_project(project_id)
    facades: list[ArchitecturalAsset] = []
    for asset in assets:
        purpose = DocumentPurpose.PROJECT_MATERIAL
        if asset.document_id is not None:
            purpose = purpose_by_doc.get(asset.document_id, DocumentPurpose.PROJECT_MATERIAL)
        facades.append(
            architectural_asset_from_parts(asset, document_purpose=purpose)
        )
    for doc in documents:
        cad_facade = architectural_asset_from_document(
            doc,
            document_purpose=purpose_by_doc.get(doc.id, DocumentPurpose.PROJECT_MATERIAL),
        )
        if cad_facade is not None:
            facades.append(cad_facade)
    return VisualEvidencePack(assets=tuple(facades))


def document_purpose_for_asset(
    document: SourceDocument | None,
) -> DocumentPurpose:
    if document is None:
        return DocumentPurpose.PROJECT_MATERIAL
    return document_purpose_from_metadata(document.metadata or {})
