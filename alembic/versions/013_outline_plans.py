"""Add outline_plans table and presentation.current_outline_id."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_outline_plans"
down_revision: str | None = "012_project_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "outline_plans" not in tables:
        op.create_table(
            "outline_plans",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("thesis", sa.Text(), nullable=False),
            sa.Column("audience", sa.String(length=500), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False),
            sa.Column("target_slide_count", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("audience_mode", sa.String(length=40), nullable=False, server_default="government"),
            sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column("logical_key", sa.String(length=200), nullable=False, server_default="presentation-outline"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_outline_plans_presentation_id", "outline_plans", ["presentation_id"])
        op.create_index("ix_outline_plans_lineage_id", "outline_plans", ["lineage_id"])

    presentation_columns = {col["name"] for col in inspector.get_columns("presentations")}
    if "current_outline_id" not in presentation_columns:
        with op.batch_alter_table("presentations") as batch_op:
            batch_op.add_column(sa.Column("current_outline_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    presentation_columns = {col["name"] for col in inspector.get_columns("presentations")}
    if "current_outline_id" in presentation_columns:
        with op.batch_alter_table("presentations") as batch_op:
            batch_op.drop_column("current_outline_id")
    if "outline_plans" in inspector.get_table_names():
        op.drop_index("ix_outline_plans_lineage_id", table_name="outline_plans")
        op.drop_index("ix_outline_plans_presentation_id", table_name="outline_plans")
        op.drop_table("outline_plans")
