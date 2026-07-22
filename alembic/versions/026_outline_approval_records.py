"""Add outline_approval_records for durable outline confirm audit."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_outline_approval_records"
down_revision: str | None = "025_delivery_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_approval_records" in tables:
        return
    op.create_table(
        "outline_approval_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outline_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("outline_revision", sa.Integer(), nullable=False),
        sa.Column("outline_hash", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["outline_id"], ["outline_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outline_approval_records_outline_id",
        "outline_approval_records",
        ["outline_id"],
    )
    op.create_index(
        "ix_outline_approval_records_presentation_id",
        "outline_approval_records",
        ["presentation_id"],
    )
    op.create_index(
        "ix_outline_approval_records_approved_at",
        "outline_approval_records",
        ["approved_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_approval_records" not in tables:
        return
    op.drop_index(
        "ix_outline_approval_records_approved_at",
        table_name="outline_approval_records",
    )
    op.drop_index(
        "ix_outline_approval_records_presentation_id",
        table_name="outline_approval_records",
    )
    op.drop_index(
        "ix_outline_approval_records_outline_id",
        table_name="outline_approval_records",
    )
    op.drop_table("outline_approval_records")
