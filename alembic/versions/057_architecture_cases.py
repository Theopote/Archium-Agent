"""Add architecture_cases table — project-scoped writable case library (Phase B)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "057_architecture_cases"
down_revision: str | None = "056_concept_direction_case_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "architecture_cases" in tables:
        return
    op.create_table(
        "architecture_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("source_knowledge_item_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("architect", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("year", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("building_type", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("design_problem", sa.Text(), nullable=False, server_default=""),
        sa.Column("strategy", sa.Text(), nullable=False, server_default=""),
        sa.Column("spatial_logic", sa.Text(), nullable=False, server_default=""),
        sa.Column("material_language", sa.Text(), nullable=False, server_default=""),
        sa.Column("atmosphere", sa.Text(), nullable=False, server_default=""),
        sa.Column("transferable_principles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("risks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_knowledge_item_id"],
            ["project_knowledge_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_architecture_cases_project_slug"),
    )
    op.create_index(
        "ix_architecture_cases_project_id",
        "architecture_cases",
        ["project_id"],
    )
    op.create_index("ix_architecture_cases_status", "architecture_cases", ["status"])
    op.create_index(
        "ix_architecture_cases_source_knowledge_item_id",
        "architecture_cases",
        ["source_knowledge_item_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "architecture_cases" not in tables:
        return
    op.drop_index(
        "ix_architecture_cases_source_knowledge_item_id",
        table_name="architecture_cases",
    )
    op.drop_index("ix_architecture_cases_status", table_name="architecture_cases")
    op.drop_index("ix_architecture_cases_project_id", table_name="architecture_cases")
    op.drop_table("architecture_cases")
