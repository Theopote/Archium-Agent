"""ArchitecturalAsset — thin read facade over SourceDocument + Asset.

No new persistence table. Bridges multimodal intake into the world model
without forking Project identity (life-system Topic 05 / DOM-031).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, DocumentPurpose
from archium.domain.knowledge_reference import KnowledgeUsage

if TYPE_CHECKING:
    from archium.domain.document import SourceDocument


class ArchitecturalAssetRole(StrEnum):
    SITE_PHOTO = "site_photo"
    DRAWING = "drawing"
    DIAGRAM = "diagram"
    CAD_BIM = "cad_bim"
    REFERENCE = "reference"
    OTHER = "other"


_DRAWING_TYPES = frozenset(
    {
        "site_plan",
        "floor_plan",
        "section",
        "elevation",
        "plan",
        "drawing",
    }
)
_PHOTO_TYPES = frozenset({"photo", "image", "site_photo"})
_DIAGRAM_TYPES = frozenset({"diagram", "chart"})
_ILLUSTRATIVE_MARKERS = frozenset(
    {
        "generated",
        "web_image",
        "stock",
        "illustrative",
        "research_vision",
        "ai_generated",
    }
)


class ArchitecturalAsset(DomainModel):
    """Unified read entry for PDF/CAD/BIM/photo assets under a Project."""

    project_id: UUID
    asset_id: UUID
    document_id: UUID | None = None
    filename: str = ""
    role: ArchitecturalAssetRole = ArchitecturalAssetRole.OTHER
    usage: KnowledgeUsage = KnowledgeUsage.BACKGROUND
    modality: str = "image"
    document_purpose: DocumentPurpose = DocumentPurpose.PROJECT_MATERIAL
    drawing_type: str = ""
    tags: list[str] = Field(default_factory=list)

    def to_input_source_line(self) -> str:
        return f"{self.role.value}:1"

    def to_prompt_line(self) -> str:
        label = self.filename or str(self.asset_id)
        return (
            f"[{self.role.value}/{self.usage.value}] {label}"
            + (f" ({self.drawing_type})" if self.drawing_type else "")
        )


def infer_architectural_asset_role(
    asset: Asset,
    *,
    document_purpose: DocumentPurpose = DocumentPurpose.PROJECT_MATERIAL,
) -> ArchitecturalAssetRole:
    """Heuristic role from AssetType, vision metadata, tags, and document purpose."""
    if document_purpose in {
        DocumentPurpose.REFERENCE_CASE,
        DocumentPurpose.REFERENCE_STYLE,
        DocumentPurpose.PUBLIC_RESEARCH,
    }:
        return ArchitecturalAssetRole.REFERENCE

    tags = {t.lower() for t in (asset.tags or [])}
    meta = asset.metadata or {}
    if tags & _ILLUSTRATIVE_MARKERS or _metadata_marks_illustrative(meta):
        return ArchitecturalAssetRole.REFERENCE

    drawing_type = str(meta.get("drawing_type") or meta.get("vision_drawing_type") or "").lower()
    if drawing_type in _DRAWING_TYPES or asset.asset_type == AssetType.DRAWING:
        return ArchitecturalAssetRole.DRAWING
    if drawing_type in _DIAGRAM_TYPES or asset.asset_type in {
        AssetType.DIAGRAM,
        AssetType.CHART,
    }:
        return ArchitecturalAssetRole.DIAGRAM
    if (
        drawing_type in _PHOTO_TYPES
        or asset.asset_type == AssetType.PHOTO
        or "site" in tags
        or "photo" in tags
    ):
        return ArchitecturalAssetRole.SITE_PHOTO
    if asset.asset_type == AssetType.IMAGE:
        # Generic image: prefer photo for project materials unless caption says drawing
        caption = str(meta.get("vision_caption") or asset.description or "").lower()
        if any(h in caption for h in ("平面", "剖面", "立面", "总平面", "plan", "section")):
            return ArchitecturalAssetRole.DRAWING
        return ArchitecturalAssetRole.SITE_PHOTO
    return ArchitecturalAssetRole.OTHER


def infer_architectural_asset_usage(
    role: ArchitecturalAssetRole,
    *,
    document_purpose: DocumentPurpose = DocumentPurpose.PROJECT_MATERIAL,
    asset: Asset | None = None,
) -> KnowledgeUsage:
    """Project materials → EVIDENCE; reference / generated → ILLUSTRATIVE."""
    if role == ArchitecturalAssetRole.REFERENCE:
        return KnowledgeUsage.ILLUSTRATIVE
    if document_purpose != DocumentPurpose.PROJECT_MATERIAL:
        return KnowledgeUsage.ILLUSTRATIVE
    if asset is not None and _metadata_marks_illustrative(asset.metadata or {}):
        return KnowledgeUsage.ILLUSTRATIVE
    if role in {
        ArchitecturalAssetRole.SITE_PHOTO,
        ArchitecturalAssetRole.DRAWING,
        ArchitecturalAssetRole.DIAGRAM,
        ArchitecturalAssetRole.CAD_BIM,
    }:
        return KnowledgeUsage.EVIDENCE
    return KnowledgeUsage.BACKGROUND


def architectural_asset_from_parts(
    asset: Asset,
    *,
    document_purpose: DocumentPurpose = DocumentPurpose.PROJECT_MATERIAL,
) -> ArchitecturalAsset:
    role = infer_architectural_asset_role(asset, document_purpose=document_purpose)
    usage = infer_architectural_asset_usage(
        role, document_purpose=document_purpose, asset=asset
    )
    meta = asset.metadata or {}
    drawing_type = str(meta.get("drawing_type") or meta.get("vision_drawing_type") or "")
    modality = _modality_for_role(role)
    return ArchitecturalAsset(
        project_id=asset.project_id,
        asset_id=asset.id,
        document_id=asset.document_id,
        filename=asset.filename,
        role=role,
        usage=usage,
        modality=modality,
        document_purpose=document_purpose,
        drawing_type=drawing_type,
        tags=list(asset.tags or []),
    )


def architectural_asset_from_document(
    document: SourceDocument,
    *,
    document_purpose: DocumentPurpose | None = None,
) -> ArchitecturalAsset | None:
    """Document-level facade for CAD/BIM (no raster Asset required)."""
    from archium.domain.document import SourceDocument
    from archium.domain.enums import DocumentType

    assert isinstance(document, SourceDocument)
    purpose = document_purpose or DocumentPurpose.PROJECT_MATERIAL
    meta = document.metadata or {}
    is_cad = bool(meta.get("cad_bim")) or document.file_type in {
        DocumentType.DWG,
        DocumentType.DXF,
        DocumentType.IFC,
        DocumentType.RVT,
    }
    if not is_cad:
        return None
    if purpose in {
        DocumentPurpose.REFERENCE_CASE,
        DocumentPurpose.REFERENCE_STYLE,
        DocumentPurpose.PUBLIC_RESEARCH,
    }:
        role = ArchitecturalAssetRole.REFERENCE
        usage = KnowledgeUsage.ILLUSTRATIVE
    else:
        role = ArchitecturalAssetRole.CAD_BIM
        usage = KnowledgeUsage.EVIDENCE
    fmt = str(meta.get("format") or document.file_type.value)
    return ArchitecturalAsset(
        project_id=document.project_id,
        asset_id=document.id,  # document-scoped facade id
        document_id=document.id,
        filename=document.filename,
        role=role,
        usage=usage,
        modality="bim" if document.file_type == DocumentType.IFC else "cad",
        document_purpose=purpose,
        drawing_type=fmt,
        tags=["cad_bim", document.file_type.value],
    )


def summarize_role_counts(assets: list[ArchitecturalAsset]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in assets:
        key = item.role.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def input_source_lines_from_assets(assets: list[ArchitecturalAsset]) -> list[str]:
    counts = summarize_role_counts(assets)
    order = (
        ArchitecturalAssetRole.SITE_PHOTO,
        ArchitecturalAssetRole.DRAWING,
        ArchitecturalAssetRole.DIAGRAM,
        ArchitecturalAssetRole.CAD_BIM,
        ArchitecturalAssetRole.REFERENCE,
        ArchitecturalAssetRole.OTHER,
    )
    return [f"{role.value}:{counts[role.value]}" for role in order if counts.get(role.value)]


def _modality_for_role(role: ArchitecturalAssetRole) -> str:
    if role == ArchitecturalAssetRole.SITE_PHOTO:
        return "photo"
    if role == ArchitecturalAssetRole.DRAWING:
        return "drawing"
    if role == ArchitecturalAssetRole.DIAGRAM:
        return "diagram"
    if role == ArchitecturalAssetRole.CAD_BIM:
        return "cad"
    return "image"


def _metadata_marks_illustrative(meta: dict[str, object]) -> bool:
    policy = str(meta.get("asset_policy") or meta.get("vision_asset_policy") or "").lower()
    if policy in {"illustrative_only", "forbidden_for_evidence", "generated"}:
        return True
    source = str(meta.get("source") or meta.get("asset_source") or "").lower()
    return source in _ILLUSTRATIVE_MARKERS or any(
        marker in source for marker in ("web_image", "generated")
    )
