"""Human-readable labels for project asset provenance."""

from __future__ import annotations

from uuid import UUID

from archium.domain.asset import Asset

_WEB_IMPORT_TAG = "web_import"


def is_web_import_asset(asset: Asset) -> bool:
    return _WEB_IMPORT_TAG in asset.tags


def format_asset_provenance(
    asset: Asset | None,
    *,
    document_names: dict[UUID, str] | None = None,
) -> str | None:
    """Return a short provenance label for Asset Board display."""
    if asset is None:
        return None
    if is_web_import_asset(asset):
        provider = str(asset.metadata.get("provider") or "网络").strip()
        attribution = asset.metadata.get("attribution")
        if isinstance(attribution, str) and attribution.strip():
            return f"网络搜图 · {provider} · {attribution.strip()}"
        return f"网络搜图 · {provider}"
    if asset.document_id is not None and document_names is not None:
        return document_names.get(asset.document_id, "项目资料")
    return "项目素材"


def format_asset_option_label(asset: Asset) -> str:
    """Label for select boxes in the Asset Board."""
    drawing_type = asset.metadata.get("drawing_type")
    type_hint = f" · {drawing_type}" if isinstance(drawing_type, str) and drawing_type else ""
    if is_web_import_asset(asset):
        provider = str(asset.metadata.get("provider") or "web").strip()
        return f"{asset.filename} · 网络/{provider}{type_hint}"
    if asset.metadata.get("vision_source"):
        source = str(asset.metadata.get("vision_source"))
        return f"{asset.filename}{type_hint} · {source}"
    return f"{asset.filename}{type_hint}"


def format_asset_vision_summary(asset: Asset) -> str | None:
    """Short vision caption for Asset Board detail."""
    vision = asset.metadata.get("vision_caption")
    if isinstance(vision, dict):
        summary = vision.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    if asset.description:
        return asset.description.strip()
    return None
