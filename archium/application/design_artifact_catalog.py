"""List DesignArtifact-stamped Assets for product chrome (Topic 07 L3)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.design_artifact import (
    DesignArtifact,
    design_artifact_from_asset,
)
from archium.infrastructure.database.repositories import AssetRepository


@dataclass(frozen=True)
class DesignArtifactRow:
    artifact: DesignArtifact
    filename: str
    asset_path: str

    def display_line(self) -> str:
        kind = self.artifact.kind.value
        seed = self.artifact.seed_source or "—"
        name = self.filename or str(self.artifact.asset_id or "")
        return f"[{kind}] {name} · seed={seed}"


def list_design_artifacts(
    session: SessionLike,
    project_id: UUID,
    *,
    limit: int = 24,
) -> list[DesignArtifactRow]:
    """Return newest DesignArtifact rows (illustrative Vision outputs)."""
    session = session_of(session)
    assets = AssetRepository(session).list_by_project(project_id)
    rows: list[DesignArtifactRow] = []
    for asset in assets:
        artifact = design_artifact_from_asset(asset)
        if artifact is None:
            continue
        rows.append(
            DesignArtifactRow(
                artifact=artifact,
                filename=asset.filename or "",
                asset_path=asset.path or "",
            )
        )

    def _sort_key(row: DesignArtifactRow) -> str:
        # Prefer prompt_hash / id for stable newest-first when timestamps unavailable
        return str(row.artifact.id)

    # Assets list is typically creation order; reverse for newest-first
    rows.reverse()
    return rows[: max(1, limit)]
