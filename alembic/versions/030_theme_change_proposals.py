"""Add theme_change_proposals table for deck-wide DesignSystem proposals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030_theme_change_proposals"
down_revision: str | None = "029_element_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "theme_change_proposals" in tables:
        return

    op.create_table(
        "theme_change_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("art_direction_id", sa.Uuid(), nullable=True),
        sa.Column("base_design_system_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_design_system_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["base_design_system_id"], ["design_systems.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["proposed_design_system_id"], ["design_systems.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_theme_change_proposals_presentation_id",
        "theme_change_proposals",
        ["presentation_id"],
    )
    op.create_index("ix_theme_change_proposals_status", "theme_change_proposals", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "theme_change_proposals" not in tables:
        return
    op.drop_index("ix_theme_change_proposals_status", table_name="theme_change_proposals")
    op.drop_index(
        "ix_theme_change_proposals_presentation_id",
        table_name="theme_change_proposals",
    )
    op.drop_table("theme_change_proposals")
