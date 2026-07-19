"""Vision captions for drawing assets and RAG chunk generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import AssetType
from archium.infrastructure.database.repositories import AssetRepository, DocumentRepository
from archium.infrastructure.llm.asset_schemas import AssetVisionCaptionDraft
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.factory import create_llm_provider
from archium.infrastructure.vision.analyzer import analyze_image
from archium.infrastructure.vision.image_loader import load_asset_image
from archium.logging import get_logger
from archium.prompts.asset_vision import (
    ASSET_VISION_SYSTEM_PROMPT,
    build_asset_vision_user_prompt,
)

logger = get_logger(__name__, operation="asset_vision_rag")

_INDEXABLE_ASSET_TYPES = {
    AssetType.DRAWING,
    AssetType.DIAGRAM,
    AssetType.IMAGE,
    AssetType.PHOTO,
    AssetType.CHART,
}
_MIN_VISION_WIDTH = 400
_MIN_VISION_HEIGHT = 300
_HEURISTIC_DRAWING_TYPES = {"photo"}


@dataclass(frozen=True)
class CaptionResult:
    draft: AssetVisionCaptionDraft
    source: str


@dataclass(frozen=True)
class AssetVisionRagResult:
    assets: list[Asset]
    chunks: list[DocumentChunk]


class AssetVisionRagService:
    """Generate vision/heuristic captions for assets and materialize RAG chunks."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._assets = AssetRepository(session)
        self._llm = llm
        if self._llm is None and self._settings.asset_vision_llm_enabled:
            self._llm = create_llm_provider(self._settings)

    def process_document_assets(
        self,
        project_id: UUID,
        document: SourceDocument,
        assets: list[Asset],
        *,
        base_chunk_index: int,
    ) -> AssetVisionRagResult:
        if not self._settings.asset_vision_rag_enabled or not assets:
            return AssetVisionRagResult(assets=assets, chunks=[])

        enriched: list[Asset] = []
        chunks: list[DocumentChunk] = []
        next_index = base_chunk_index

        for asset in assets:
            if not self._should_index_asset(asset):
                enriched.append(asset)
                continue
            try:
                caption = self._caption_asset(asset)
                updated = self._persist_asset_caption(asset, caption)
                chunk = DocumentChunk(
                    project_id=project_id,
                    document_id=document.id,
                    content=build_asset_caption_chunk_text(
                        updated,
                        caption.draft,
                        document_name=document.filename,
                    ),
                    page_number=updated.page_number,
                    section_title=updated.filename,
                    content_type="asset_caption",
                    chunk_index=next_index,
                    metadata={
                        "asset_id": str(updated.id),
                        "drawing_type": caption.draft.drawing_type,
                        "vision_source": caption.source,
                    },
                )
                next_index += 1
                enriched.append(updated)
                chunks.append(chunk)
            except Exception as exc:
                logger.warning("Asset vision RAG skipped for %s: %s", asset.filename, exc)
                enriched.append(asset)

        if chunks:
            logger.info(
                "Prepared %d asset caption chunk(s) for document %s",
                len(chunks),
                document.filename,
            )
        return AssetVisionRagResult(assets=enriched, chunks=chunks)

    def _should_index_asset(self, asset: Asset) -> bool:
        if asset.asset_type not in _INDEXABLE_ASSET_TYPES:
            return False
        if asset.width is not None and asset.width < _MIN_VISION_WIDTH:
            return False
        if asset.height is not None and asset.height < _MIN_VISION_HEIGHT:
            return False
        return Path(asset.path).is_file()

    def _caption_asset(self, asset: Asset) -> CaptionResult:
        heuristic = self._heuristic_caption(asset)
        if not self._vision_llm_available():
            return heuristic
        try:
            llm_caption = self._llm_caption(asset)
        except Exception as exc:
            logger.warning("LLM asset caption failed for %s: %s", asset.filename, exc)
            return heuristic
        return llm_caption or heuristic

    def _vision_llm_available(self) -> bool:
        return bool(
            self._settings.asset_vision_llm_enabled
            and self._settings.llm_configured
            and self._llm is not None
        )

    def _heuristic_caption(self, asset: Asset) -> CaptionResult:
        drawing_type = "unknown"
        try:
            image = load_asset_image(asset)
            report = analyze_image(asset.id, asset.path, image)
            drawing_type = report.drawing_type or "unknown"
        except Exception:
            drawing_type = "unknown"

        size_label = (
            f"{asset.width}×{asset.height}"
            if asset.width and asset.height
            else "未知尺寸"
        )
        summary = (
            f"{asset.filename} 建筑图档，分类倾向 {drawing_type}，尺寸 {size_label}。"
            "（启发式描述，未启用或未成功运行 Vision LLM。）"
        )
        return CaptionResult(
            draft=AssetVisionCaptionDraft(
                drawing_type=drawing_type,
                summary=summary,
                spatial_elements=[],
                annotations=[],
                metrics_visible=[],
            ),
            source="heuristic",
        )

    def _llm_caption(self, asset: Asset) -> CaptionResult | None:
        assert self._llm is not None
        model = self._settings.asset_vision_llm_model or self._settings.llm_model
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=ASSET_VISION_SYSTEM_PROMPT,
                user_prompt=build_asset_vision_user_prompt(
                    filename=asset.filename,
                    page_number=asset.page_number,
                ),
                model=model,
                temperature=0.2,
                json_mode=True,
                image_paths=(asset.path,),
            ),
            AssetVisionCaptionDraft,
        )
        return CaptionResult(draft=draft, source="llm_vision")

    def _persist_asset_caption(
        self,
        asset: Asset,
        caption: CaptionResult,
    ) -> Asset:
        payload = caption.draft.model_dump()
        payload["vision_source"] = caption.source
        asset.description = caption.draft.summary.strip()
        asset.metadata = {
            **asset.metadata,
            "vision_caption": payload,
            "drawing_type": caption.draft.drawing_type,
            "vision_source": caption.source,
        }
        tags = {tag.strip().lower() for tag in asset.tags if tag.strip()}
        tags.add(caption.draft.drawing_type.strip().lower())
        if caption.draft.drawing_type not in _HEURISTIC_DRAWING_TYPES:
            tags.add("drawing")
        asset.tags = sorted(tags)
        return self._assets.update(asset)


@dataclass(frozen=True)
class AssetVisionBackfillResult:
    assets_processed: int
    chunks_created: int


class AssetVisionBackfillService:
    """Backfill vision captions + RAG chunks for assets imported before P2."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._assets = AssetRepository(session)
        self._documents = DocumentRepository(session)
        self._vision = AssetVisionRagService(session, llm=llm, settings=self._settings)

    def backfill_project(self, project_id: UUID) -> AssetVisionBackfillResult:
        if not self._settings.asset_vision_rag_enabled:
            return AssetVisionBackfillResult(assets_processed=0, chunks_created=0)

        from archium.application.fact_extraction_service import FactExtractionService
        from archium.application.retrieval_service import create_retrieval_service

        assets_processed = 0
        chunks_created = 0
        assets_by_document: dict[UUID, list[Asset]] = {}
        for asset in self._assets.list_by_project(project_id):
            if asset.document_id is None:
                continue
            assets_by_document.setdefault(asset.document_id, []).append(asset)

        retrieval = create_retrieval_service(self._session, self._settings)
        fact_extractor = FactExtractionService(self._session, settings=self._settings)

        for document_id, document_assets in assets_by_document.items():
            document = self._documents.get_document(document_id)
            if document is None:
                continue
            existing_ids = self._existing_caption_asset_ids(document_id)
            pending = [
                asset
                for asset in document_assets
                if str(asset.id) not in existing_ids and self._vision._should_index_asset(asset)
            ]
            if not pending:
                continue
            base_index = self._next_chunk_index(document_id)
            result = self._vision.process_document_assets(
                project_id,
                document,
                pending,
                base_chunk_index=base_index,
            )
            saved: list[DocumentChunk] = []
            for chunk in result.chunks:
                saved.append(self._documents.create_chunk(chunk))
            if saved:
                fact_extractor.extract_from_document(
                    project_id,
                    document_name=document.filename,
                    chunks=saved,
                )
                retrieval.index_chunks(project_id, saved, document_name=document.filename)
            assets_processed += len(pending)
            chunks_created += len(saved)

        if chunks_created:
            logger.info(
                "Backfilled %d asset caption chunk(s) for project %s",
                chunks_created,
                project_id,
            )
        return AssetVisionBackfillResult(
            assets_processed=assets_processed,
            chunks_created=chunks_created,
        )

    def _existing_caption_asset_ids(self, document_id: UUID) -> set[str]:
        return {
            str(chunk.metadata.get("asset_id"))
            for chunk in self._documents.list_chunks(document_id)
            if chunk.content_type == "asset_caption" and chunk.metadata.get("asset_id")
        }

    def _next_chunk_index(self, document_id: UUID) -> int:
        chunks = self._documents.list_chunks(document_id)
        if not chunks:
            return 0
        return max(chunk.chunk_index for chunk in chunks) + 1


def build_asset_caption_chunk_text(
    asset: Asset,
    caption: AssetVisionCaptionDraft,
    *,
    document_name: str,
) -> str:
    lines = [
        f"【图纸资产 · {caption.drawing_type}】",
        f"文件名：{asset.filename}",
        f"来源文档：{document_name}",
    ]
    if asset.page_number is not None:
        lines.append(f"页码：p.{asset.page_number}")
    if asset.width and asset.height:
        lines.append(f"尺寸：{asset.width}×{asset.height}")
    lines.append(f"摘要：{caption.summary.strip()}")
    if caption.spatial_elements:
        lines.append("空间要素：" + "、".join(caption.spatial_elements))
    if caption.annotations:
        lines.append("标注说明：" + "、".join(caption.annotations))
    if caption.metrics_visible:
        lines.append("可见指标：" + "、".join(caption.metrics_visible))
    if caption.scale_or_north:
        lines.append(f"比例/指北：{caption.scale_or_north.strip()}")
    return "\n".join(lines)
