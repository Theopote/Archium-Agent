"""Add project knowledge items table for provenance-tracked statements."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_project_knowledge"
down_revision: str | None = "011_visual_composition"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "project_knowledge_items" not in tables:
        op.create_table(
            "project_knowledge_items",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("origin", sa.String(length=40), nullable=False),
            sa.Column("reliability", sa.String(length=40), nullable=False),
            sa.Column("source_citations", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column(
                "applies_to_current_project",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "requires_user_confirmation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("conflict_group", sa.String(length=100)),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("category", sa.String(length=100), nullable=False, server_default="general"),
            sa.Column("linked_fact_id", sa.Uuid()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_project_knowledge_items_project_id",
            "project_knowledge_items",
            ["project_id"],
        )
        op.create_index(
            "ix_project_knowledge_items_status",
            "project_knowledge_items",
            ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_knowledge_items" in inspector.get_table_names():
        op.drop_index("ix_project_knowledge_items_status", table_name="project_knowledge_items")
        op.drop_index(
            "ix_project_knowledge_items_project_id",
            table_name="project_knowledge_items",
        )
        op.drop_table("project_knowledge_items")
