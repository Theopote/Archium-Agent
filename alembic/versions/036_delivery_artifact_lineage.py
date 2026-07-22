"""Add artifact lineage metadata to delivery records.

Revision ID: 036_delivery_artifact_lineage
Revises: 035_project_mission_approval_hash
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "036_delivery_artifact_lineage"
down_revision: str | None = "035_project_mission_approval_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "delivery_records",
        sa.Column("artifact_kind", sa.String(50), nullable=False, server_default="pptx"),
    )
    op.add_column(
        "delivery_records",
        sa.Column("derived_from_artifact_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "delivery_records",
        sa.Column(
            "generator_version",
            sa.String(100),
            nullable=False,
            server_default="archium-unknown",
        ),
    )
    op.add_column("delivery_records", sa.Column("font_manifest_hash", sa.String(128)))
    op.add_column("delivery_records", sa.Column("theme_version", sa.String(100)))
    op.add_column("delivery_records", sa.Column("export_policy", sa.String(100)))


def downgrade() -> None:
    for column in (
        "export_policy",
        "theme_version",
        "font_manifest_hash",
        "generator_version",
        "derived_from_artifact_ids",
        "artifact_kind",
    ):
        op.drop_column("delivery_records", column)
