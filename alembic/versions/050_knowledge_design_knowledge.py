"""Add design_knowledge JSON on project_knowledge_items."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "050_knowledge_design_knowledge"
down_revision: str | None = "049_visual_brief_optional_mission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "project_knowledge_items" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("project_knowledge_items")}
    if "design_knowledge" in columns:
        return
    with op.batch_alter_table("project_knowledge_items") as batch:
        batch.add_column(sa.Column("design_knowledge", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "project_knowledge_items" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("project_knowledge_items")}
    if "design_knowledge" not in columns:
        return
    with op.batch_alter_table("project_knowledge_items") as batch:
        batch.drop_column("design_knowledge")
