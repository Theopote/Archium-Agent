"""Structured element-edit intents for Studio element comments."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel

ElementEditOperation = Literal[
    "move",
    "resize",
    "align",
    "distribute",
    "replace_asset",
    "rewrite_text",
    "change_style",
    "visibility",
    "lock",
    "reorder",
]

ElementEditIntentSource = Literal["keyword", "structured_model", "heuristic"]


class ElementEditIntent(DomainModel):
    """Compact structured intent — keywords fill this; LLM emits this schema.

    Compilers map one intent to one or more ``StudioCommand`` values. Do not grow
    unbounded keyword tables; add operations / fields here instead.
    """

    operation: ElementEditOperation
    direction: str | None = None
    amount: float | None = None
    reference_node_ids: list[str] = Field(default_factory=list)

    # Operation-specific payloads (optional; leave unset when not applicable).
    text_value: str | None = None
    color_value: str | None = None
    font_size: float | None = None
    asset_uri: str | None = None
    asset_id: UUID | None = None
    locked: bool | None = None
    visible: bool | None = None
    match_dimension: Literal["width", "height", "both"] | None = None

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: ElementEditIntentSource = "keyword"
    rationale: str = ""
