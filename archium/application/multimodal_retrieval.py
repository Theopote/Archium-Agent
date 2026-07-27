"""Multimodal architectural retrieval — captions today, image/CAD hooks tomorrow.

Service only. Reuses asset_caption chunks + vision metadata; optional
ImageEmbeddingProvider protocol for future CLIP-style backends (not default).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field
from sqlalchemy.orm import Session

from archium.application.retrieval_credibility import rank_relevance, score_chunk_credibility
from archium.application.retrieval_filters import RetrievalFilters
from archium.application.retrieval_hybrid import keyword_overlap_score
from archium.application.retrieval_service import create_retrieval_service
from archium.config.settings import Settings, get_settings
from archium.domain._base import DomainModel
from archium.domain.architectural_chunk import ArchitecturalChunkType
from archium.domain.document import DocumentChunk
from archium.domain.knowledge_reference import (
    KnowledgeReference,
    KnowledgeSourceKind,
    KnowledgeUsage,
)
from archium.infrastructure.database.repositories import DocumentRepository


class MultimodalModality(StrEnum):
    IMAGE = "image"
    DRAWING = "drawing"
    DIAGRAM = "diagram"
    PHOTO = "photo"
    CAD = "cad"  # reserved — no IFC/DWG parser yet
    BIM = "bim"  # reserved
    TEXT = "text"


class VisualFeatureAnnotation(DomainModel):
    """Structured visual understanding proxy (from caption / future VLM)."""

    modality: MultimodalModality = MultimodalModality.IMAGE
    spatial_features: list[str] = Field(default_factory=list)
    material_cues: list[str] = Field(default_factory=list)
    style_cues: list[str] = Field(default_factory=list)
    drawing_type: str = ""
    problems: list[str] = Field(default_factory=list)
    raw_caption: str = ""

    def to_prompt_block(self) -> str:
        lines = [f"模态：{self.modality.value}"]
        if self.drawing_type:
            lines.append(f"图纸类型：{self.drawing_type}")
        if self.spatial_features:
            lines.append("空间：" + "、".join(self.spatial_features[:6]))
        if self.material_cues:
            lines.append("材料：" + "、".join(self.material_cues[:6]))
        if self.style_cues:
            lines.append("风格：" + "、".join(self.style_cues[:6]))
        if self.problems:
            lines.append("问题：" + "、".join(self.problems[:4]))
        if self.raw_caption.strip():
            lines.append(self.raw_caption.strip()[:240])
        return "\n".join(lines)


class ImageEmbeddingProvider(Protocol):
    """Future CLIP / vision embedding backend (optional)."""

    def embed_images(self, paths: list[str]) -> list[list[float]]: ...


_SPATIAL_HINTS = ("院落", "流线", "轴线", "围合", "入口", "庭院", "台地", "路径", "courtyard")
_MATERIAL_HINTS = ("砖", "木", "混凝土", "石", "瓦", "玻璃", "金属", "material")
_STYLE_HINTS = ("现代", "传统", "极简", "地域", "industrial", "vernacular")
_DRAWING_HINTS = ("平面", "剖面", "立面", "总平面", "图纸", "plan", "section", "elevation")
_PHOTO_HINTS = ("照片", "实景", "photo", "现场")


def infer_modality_from_query(query: str) -> MultimodalModality | None:
    text = (query or "").lower()
    if not text:
        return None
    if any(h in text for h in ("bim", "ifc", "revit")):
        return MultimodalModality.BIM
    if any(h in text for h in ("cad", "dwg", "dxf", "线稿")):
        return MultimodalModality.CAD
    if any(h in text for h in _DRAWING_HINTS):
        return MultimodalModality.DRAWING
    if any(h in text for h in _PHOTO_HINTS):
        return MultimodalModality.PHOTO
    if any(h in text for h in ("图", "image", "视觉", "示意")):
        return MultimodalModality.IMAGE
    return None


def annotate_from_caption_chunk(chunk: DocumentChunk) -> VisualFeatureAnnotation:
    caption = chunk.content or ""
    drawing_type = str(chunk.metadata.get("drawing_type") or "")
    modality = MultimodalModality.DRAWING
    if drawing_type in {"photo", "image"} or chunk.content_type == "image":
        modality = MultimodalModality.PHOTO
    elif drawing_type in {"site_plan", "floor_plan", "section", "elevation", "plan"}:
        modality = MultimodalModality.DRAWING
    elif "diagram" in drawing_type.lower() or (
        "示意" in caption and not drawing_type
    ):
        modality = MultimodalModality.DIAGRAM

    lower = caption.lower()
    return VisualFeatureAnnotation(
        modality=modality,
        spatial_features=[h for h in _SPATIAL_HINTS if h.lower() in lower][:6],
        material_cues=[h for h in _MATERIAL_HINTS if h.lower() in lower][:6],
        style_cues=[h for h in _STYLE_HINTS if h.lower() in lower][:6],
        drawing_type=drawing_type,
        problems=[],
        raw_caption=caption[:800],
    )


class MultimodalRetrievalService:
    """Retrieve visual/architectural media via caption RAG + feature annotations."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        image_embedder: ImageEmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._documents = DocumentRepository(session)
        self._image_embedder = image_embedder  # reserved for future CLIP path

    @property
    def image_embeddings_available(self) -> bool:
        return self._image_embedder is not None

    def retrieve(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int = 6,
    ) -> list[KnowledgeReference]:
        query = (query or "").strip()
        modality = infer_modality_from_query(query)
        # Always allow multimodal channel when query mentions visual/drawing OR blank modality with asset preference
        if (
            modality is None
            and not any(token in query for token in ("空间", "材料", "立面", "氛围", "示意"))
            and not self._settings.asset_vision_rag_enabled
        ):
            # Soft: still scan captions if asset_vision enabled and query non-empty
            return []

        filters = RetrievalFilters(content_types=("asset_caption", "image"))
        retrieval = create_retrieval_service(self._session, self._settings)
        chunks: list[DocumentChunk] = []
        if query and retrieval.available:
            chunks = retrieval.retrieve(
                project_id,
                query,
                top_k=max(top_k * 2, top_k),
                filters=filters,
            )
        if not chunks:
            # Fallback: list caption chunks from project
            chunks = [
                chunk
                for chunk in self._documents.list_chunks_by_project(project_id)
                if chunk.content_type in {"asset_caption", "image"}
            ][: top_k * 2]

        refs: list[KnowledgeReference] = []
        for chunk in chunks:
            annotation = annotate_from_caption_chunk(chunk)
            if modality is not None and modality in {
                MultimodalModality.DRAWING,
                MultimodalModality.PHOTO,
                MultimodalModality.DIAGRAM,
                MultimodalModality.IMAGE,
            }:
                # Soft preference: boost matching modality
                pass
            similarity = keyword_overlap_score(query, chunk.content) if query else 0.4
            if modality == MultimodalModality.DRAWING and annotation.modality == MultimodalModality.DRAWING:
                similarity = min(1.0, similarity + 0.2)
            if modality == MultimodalModality.PHOTO and annotation.modality == MultimodalModality.PHOTO:
                similarity = min(1.0, similarity + 0.15)
            # Feature overlap boost
            feature_blob = " ".join(
                annotation.spatial_features + annotation.material_cues + annotation.style_cues
            )
            if feature_blob and query:
                similarity = max(similarity, keyword_overlap_score(query, feature_blob) * 0.9)

            cred = score_chunk_credibility(chunk)
            content = annotation.to_prompt_block()
            usage = self._usage_for_chunk(chunk)
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.MULTIMODAL_ASSET,
                    source_id=str(chunk.id),
                    content=content[:1500],
                    title=(annotation.drawing_type or "视觉资产")[:120],
                    similarity=max(0.2, similarity),
                    authority=cred.authority,
                    transferability=cred.transferability,
                    relevance=rank_relevance(
                        similarity=max(0.2, similarity),
                        authority=cred.authority,
                        transferability=cred.transferability,
                        usage=usage,
                    ),
                    usage=usage,
                    architectural_type=ArchitecturalChunkType.DRAWING_NOTE,
                    project_id=project_id,
                    extra={
                        "modality": annotation.modality.value,
                        "drawing_type": annotation.drawing_type,
                        "spatial_features": annotation.spatial_features,
                        "material_cues": annotation.material_cues,
                        "asset_id": str(chunk.metadata.get("asset_id") or ""),
                        "image_embedding": False,
                        "cad_bim_ready": False,
                        "usage": usage.value,
                    },
                )
            )

        # Reserved CAD/BIM: prefer project IFC text semantics when present
        if modality in {MultimodalModality.CAD, MultimodalModality.BIM}:
            cad_ready = self._project_has_cad_text_semantics(project_id)
            if cad_ready:
                refs.append(
                    KnowledgeReference(
                        source_kind=KnowledgeSourceKind.MULTIMODAL_ASSET,
                        source_id=f"advisory:{modality.value}:ready",
                        content=(
                            "项目已登记 CAD/BIM 文本语义（IFC 实体计数/空间名称）；"
                            "完整几何/拓扑仍未接入。请结合 constraints / floors 事实与 cad_bim 证据通道。"
                        ),
                        title=f"{modality.value.upper()} 文本语义已就绪",
                        similarity=0.55,
                        authority=0.85,
                        transferability=0.55,
                        relevance=0.5,
                        usage=KnowledgeUsage.EVIDENCE,
                        project_id=project_id,
                        extra={"cad_bim_ready": True, "modality": modality.value},
                    )
                )
            else:
                refs.append(
                    KnowledgeReference(
                        source_kind=KnowledgeSourceKind.MULTIMODAL_ASSET,
                        source_id=f"advisory:{modality.value}",
                        content=(
                            f"查询涉及 {modality.value.upper()}，当前仅支持 IFC 文本语义与图纸/照片 caption；"
                            "完整几何解析尚未接入。请上传 IFC 或导出图纸截图。"
                        ),
                        title=f"{modality.value.upper()} 几何未就绪",
                        similarity=0.4,
                        authority=0.9,
                        transferability=0.3,
                        relevance=0.35,
                        usage=KnowledgeUsage.BACKGROUND,
                        project_id=project_id,
                        extra={"cad_bim_ready": False, "modality": modality.value},
                    )
                )

        refs.sort(key=lambda item: item.relevance, reverse=True)
        return refs[: max(1, top_k)]

    def _project_has_cad_text_semantics(self, project_id: UUID) -> bool:
        for doc in self._documents.list_by_project(project_id):
            meta = doc.metadata or {}
            if not meta.get("cad_bim"):
                continue
            if meta.get("parse_depth") == "ifc_text_semantics":
                return True
            analysis = meta.get("analysis")
            if isinstance(analysis, dict) and analysis.get("ifc_semantics"):
                return True
            if meta.get("space_count") or meta.get("storey_count"):
                return True
        return False

    def _usage_for_chunk(self, chunk: DocumentChunk) -> KnowledgeUsage:
        """Project-material photos/drawings → EVIDENCE; reference/generated → ILLUSTRATIVE."""
        from archium.application.knowledge_isolation import document_purpose_from_metadata
        from archium.domain.architectural_asset import (
            ArchitecturalAssetRole,
            infer_architectural_asset_role,
            infer_architectural_asset_usage,
        )
        from archium.domain.asset import Asset
        from archium.domain.enums import AssetType, DocumentPurpose
        from archium.infrastructure.database.repositories import AssetRepository

        purpose = DocumentPurpose.PROJECT_MATERIAL
        document = self._documents.get_document(chunk.document_id)
        if document is not None:
            purpose = document_purpose_from_metadata(document.metadata or {})

        asset: Asset | None = None
        raw_asset_id = chunk.metadata.get("asset_id")
        if raw_asset_id:
            try:
                asset = AssetRepository(self._session).get_by_id(UUID(str(raw_asset_id)))
            except (ValueError, TypeError):
                asset = None

        if asset is None:
            # Caption-only fallback from chunk metadata
            drawing_type = str(chunk.metadata.get("drawing_type") or "")
            proxy = Asset(
                project_id=chunk.project_id,
                document_id=chunk.document_id,
                filename="caption",
                path="caption",
                asset_type=(
                    AssetType.DRAWING
                    if drawing_type in {"site_plan", "floor_plan", "section", "elevation", "plan"}
                    else AssetType.PHOTO
                    if chunk.content_type == "image" or drawing_type in {"photo", "image"}
                    else AssetType.IMAGE
                ),
                metadata=dict(chunk.metadata or {}),
            )
            role = infer_architectural_asset_role(proxy, document_purpose=purpose)
            return infer_architectural_asset_usage(
                role, document_purpose=purpose, asset=proxy
            )

        role = infer_architectural_asset_role(asset, document_purpose=purpose)
        if role == ArchitecturalAssetRole.OTHER and annotation_hints_drawing(chunk):
            role = ArchitecturalAssetRole.DRAWING
        return infer_architectural_asset_usage(
            role, document_purpose=purpose, asset=asset
        )


def annotation_hints_drawing(chunk: DocumentChunk) -> bool:
    drawing_type = str(chunk.metadata.get("drawing_type") or "").lower()
    return drawing_type in {
        "site_plan",
        "floor_plan",
        "section",
        "elevation",
        "plan",
        "drawing",
    }
