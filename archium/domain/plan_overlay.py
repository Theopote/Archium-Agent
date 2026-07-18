"""Plan drawing overlay metadata stored on assets (north, scale, legend)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.asset import Asset

PLAN_NORTH_ARROW_KEY = "plan_north_arrow"
PLAN_SCALE_LABEL_KEY = "plan_scale_label"
PLAN_SCALE_PENDING_KEY = "plan_scale_pending"
PLAN_LEGEND_KEY = "plan_legend"


class PlanLegendItem(DomainModel):
    """One legend swatch with a user-provided label."""

    label: str = Field(min_length=1)
    color: str | None = None


class PlanOverlayMetadata(DomainModel):
    """Verified overlay annotations for site-plan style slides."""

    show_north_arrow: bool = False
    scale_label: str | None = None
    scale_pending: bool = False
    legend_items: list[PlanLegendItem] = Field(default_factory=list)

    @property
    def has_any_overlay(self) -> bool:
        return (
            self.show_north_arrow
            or bool(self.scale_label)
            or self.scale_pending
            or bool(self.legend_items)
        )


def plan_overlay_from_asset(asset: Asset | None) -> PlanOverlayMetadata | None:
    """Parse overlay metadata from an asset. Returns None when asset is missing."""
    if asset is None:
        return None
    meta = asset.metadata
    if not isinstance(meta, dict) or not meta:
        return PlanOverlayMetadata()

    legend_raw = meta.get(PLAN_LEGEND_KEY)
    legend_items: list[PlanLegendItem] = []
    if isinstance(legend_raw, list):
        for item in legend_raw:
            if isinstance(item, dict) and item.get("label"):
                legend_items.append(
                    PlanLegendItem(
                        label=str(item["label"]),
                        color=str(item["color"]) if item.get("color") else None,
                    )
                )

    scale_label = meta.get(PLAN_SCALE_LABEL_KEY)
    return PlanOverlayMetadata(
        show_north_arrow=bool(meta.get(PLAN_NORTH_ARROW_KEY)),
        scale_label=str(scale_label).strip() if isinstance(scale_label, str) and scale_label.strip() else None,
        scale_pending=bool(meta.get(PLAN_SCALE_PENDING_KEY)),
        legend_items=legend_items,
    )


def plan_overlay_to_metadata(overlay: PlanOverlayMetadata) -> dict[str, Any]:
    """Serialize overlay metadata for Asset.metadata persistence."""
    payload: dict[str, Any] = {}
    if overlay.show_north_arrow:
        payload[PLAN_NORTH_ARROW_KEY] = True
    if overlay.scale_label:
        payload[PLAN_SCALE_LABEL_KEY] = overlay.scale_label
    if overlay.scale_pending:
        payload[PLAN_SCALE_PENDING_KEY] = True
    if overlay.legend_items:
        payload[PLAN_LEGEND_KEY] = [
            {"label": item.label, **({"color": item.color} if item.color else {})}
            for item in overlay.legend_items
        ]
    return payload
