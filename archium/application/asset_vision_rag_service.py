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
from archium.infrastructure.database.repositories import AssetRepository
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
            drawing_type = report.drawing_type
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
