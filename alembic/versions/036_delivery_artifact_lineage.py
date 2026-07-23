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

_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("artifact_kind", sa.Column("artifact_kind", sa.String(50), nullable=False, server_default="pptx")),
    (
        "derived_from_artifact_ids",
        sa.Column("derived_from_artifact_ids", sa.JSON(), nullable=False, server_default="[]"),
    ),
    (
        "generator_version",
        sa.Column(
            "generator_version",
            sa.String(100),
            nullable=False,
            server_default="archium-unknown",
        ),
    ),
    ("font_manifest_hash", sa.Column("font_manifest_hash", sa.String(128))),
    ("theme_version", sa.Column("theme_version", sa.String(100))),
    ("export_policy", sa.Column("export_policy", sa.String(100))),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "delivery_records" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("delivery_records")}
    for name, column in _COLUMNS:
        if name not in columns:
            op.add_column("delivery_records", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "delivery_records" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("delivery_records")}
    for name, _column in reversed(_COLUMNS):
        if name in columns:
            op.drop_column("delivery_records", name)
