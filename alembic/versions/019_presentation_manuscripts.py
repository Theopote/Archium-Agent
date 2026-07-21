"""Add presentation_manuscripts and outline_plans.manuscript_id."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019_presentation_manuscripts"
down_revision: str | None = "018_architectural_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "presentation_manuscripts" not in tables:
        op.create_table(
            "presentation_manuscripts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column(
                "logical_key",
                sa.String(length=200),
                nullable=False,
                server_default="presentation-manuscript",
            ),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_presentation_manuscripts_project_id",
            "presentation_manuscripts",
            ["project_id"],
        )
        op.create_index(
            "ix_presentation_manuscripts_presentation_id",
            "presentation_manuscripts",
            ["presentation_id"],
        )
        op.create_index(
            "ix_presentation_manuscripts_lineage_id",
            "presentation_manuscripts",
            ["lineage_id"],
        )

    if "outline_plans" in tables:
        columns = {col["name"] for col in inspector.get_columns("outline_plans")}
        if "manuscript_id" not in columns:
            op.add_column(
                "outline_plans",
                sa.Column("manuscript_id", sa.Uuid(), nullable=True),
            )
            op.create_index(
                "ix_outline_plans_manuscript_id",
                "outline_plans",
                ["manuscript_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "outline_plans" in tables:
        columns = {col["name"] for col in inspector.get_columns("outline_plans")}
        if "manuscript_id" in columns:
            op.drop_index("ix_outline_plans_manuscript_id", table_name="outline_plans")
            op.drop_column("outline_plans", "manuscript_id")

    if "presentation_manuscripts" in tables:
        op.drop_table("presentation_manuscripts")
