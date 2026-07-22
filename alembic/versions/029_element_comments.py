"""Add element_comments table for node-bound Studio NL comments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "029_element_comments"
down_revision: str | None = "028_delivery_round_trip_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" in tables:
        return

    op.create_table(
        "element_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("slide_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.String(length=200), nullable=False),
        sa.Column("layout_element_id", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_element_comments_slide_id", "element_comments", ["slide_id"])
    op.create_index(
        "ix_element_comments_presentation_id", "element_comments", ["presentation_id"]
    )
    op.create_index("ix_element_comments_status", "element_comments", ["status"])
    op.create_index("ix_element_comments_proposal_id", "element_comments", ["proposal_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" not in tables:
        return
    op.drop_index("ix_element_comments_proposal_id", table_name="element_comments")
    op.drop_index("ix_element_comments_status", table_name="element_comments")
    op.drop_index("ix_element_comments_presentation_id", table_name="element_comments")
    op.drop_index("ix_element_comments_slide_id", table_name="element_comments")
    op.drop_table("element_comments")
