"""Add knowledge_state and intent_evolution JSON on projects."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045_knowledge_state"
down_revision: str | None = "044_idea_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "projects" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    with op.batch_alter_table("projects") as batch:
        if "knowledge_state" not in columns:
            batch.add_column(sa.Column("knowledge_state", sa.JSON(), nullable=True))
        if "intent_evolution" not in columns:
            batch.add_column(sa.Column("intent_evolution", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "projects" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    with op.batch_alter_table("projects") as batch:
        if "intent_evolution" in columns:
            batch.drop_column("intent_evolution")
        if "knowledge_state" in columns:
            batch.drop_column("knowledge_state")
