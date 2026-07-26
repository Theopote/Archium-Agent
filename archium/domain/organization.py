"""Organization — thin tenant root for multi-client studios (DOM-032).

Not full SaaS tenancy: membership stays on ProjectMember. Organization only
groups projects under one firm / client account for future billing & visibility.
"""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import IdentifiedModel, TimestampedModel


class Organization(IdentifiedModel, TimestampedModel):
    """Studio / firm / client account that may own many projects."""

    name: str = Field(min_length=1, max_length=300)
    slug: str | None = Field(
        default=None,
        max_length=80,
        description="Optional URL-ish key; unique when set.",
    )
    display_name: str = Field(
        default="",
        max_length=300,
        description="Optional brand label; falls back to name.",
    )

    def label(self) -> str:
        text = (self.display_name or "").strip() or self.name.strip()
        return text
