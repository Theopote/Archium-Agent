"""Add design_rationale JSON to concept_directions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "047_concept_direction_design_rationale"
down_revision: str | None = "046_concept_direction_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    if "design_rationale" not in columns:
        with op.batch_alter_table("concept_directions") as batch:
            batch.add_column(sa.Column("design_rationale", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    if "design_rationale" in columns:
        with op.batch_alter_table("concept_directions") as batch:
            batch.drop_column("design_rationale")
