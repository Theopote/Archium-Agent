"""Add knowledge_graph_edges — confirmed Design Knowledge Graph edges (Phase C)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "058_knowledge_graph_edges"
down_revision: str | None = "057_architecture_cases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "knowledge_graph_edges" in tables:
        return
    op.create_table(
        "knowledge_graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=40), nullable=False),
        sa.Column("source_ref", sa.String(length=120), nullable=False),
        sa.Column("target_ref", sa.String(length=120), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="user"),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_item_id"],
            ["project_knowledge_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "relation",
            "source_ref",
            "target_ref",
            name="uq_knowledge_graph_edges_project_rel_endpoints",
        ),
    )
    op.create_index(
        "ix_knowledge_graph_edges_project_id",
        "knowledge_graph_edges",
        ["project_id"],
    )
    op.create_index(
        "ix_knowledge_graph_edges_status",
        "knowledge_graph_edges",
        ["status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "knowledge_graph_edges" not in tables:
        return
    op.drop_index("ix_knowledge_graph_edges_status", table_name="knowledge_graph_edges")
    op.drop_index("ix_knowledge_graph_edges_project_id", table_name="knowledge_graph_edges")
    op.drop_table("knowledge_graph_edges")
