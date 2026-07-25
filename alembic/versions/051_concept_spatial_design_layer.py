"""Add spatial_intent + design_rules JSON on concept_directions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "051_concept_spatial_design_layer"
down_revision: str | None = "050_knowledge_design_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    with op.batch_alter_table("concept_directions") as batch:
        if "spatial_intent" not in columns:
            batch.add_column(sa.Column("spatial_intent", sa.JSON(), nullable=True))
        if "design_rules" not in columns:
            batch.add_column(
                sa.Column("design_rules", sa.JSON(), nullable=False, server_default="[]")
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    with op.batch_alter_table("concept_directions") as batch:
        if "design_rules" in columns:
            batch.drop_column("design_rules")
        if "spatial_intent" in columns:
            batch.drop_column("spatial_intent")
