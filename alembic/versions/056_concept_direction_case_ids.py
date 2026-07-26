"""Add reference_case_ids to concept_directions (Phase A knowledge links)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "056_concept_direction_case_ids"
down_revision: str | None = "055_project_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    if "reference_case_ids" in columns:
        return
    with op.batch_alter_table("concept_directions") as batch:
        batch.add_column(
            sa.Column(
                "reference_case_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    if "reference_case_ids" not in columns:
        return
    with op.batch_alter_table("concept_directions") as batch:
        batch.drop_column("reference_case_ids")
