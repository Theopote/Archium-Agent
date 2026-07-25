"""Add knowledge_state_history JSON on projects."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "048_knowledge_state_history"
down_revision: str | None = "047_concept_direction_design_rationale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "projects" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    if "knowledge_state_history" in columns:
        return
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("knowledge_state_history", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "projects" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    if "knowledge_state_history" not in columns:
        return
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("knowledge_state_history")
