"""Explainable visual QA models for slide-bound assets."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class VisualQACheck(DomainModel):
    """Result of one interpretable image check."""

    check_name: str = Field(min_length=1)
    passed: bool
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    evidence: dict[str, object] = Field(default_factory=dict)


class VisualQAReport(DomainModel):
    """Aggregated visual QA for one asset image."""

    asset_id: UUID
    asset_path: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    drawing_type: str | None = None
    drawing_type_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    checks: list[VisualQACheck] = Field(default_factory=list)

    def check(self, name: str) -> VisualQACheck | None:
        for item in self.checks:
            if item.check_name == name:
                return item
        return None

    def failed_checks(self) -> list[VisualQACheck]:
        return [item for item in self.checks if not item.passed]
