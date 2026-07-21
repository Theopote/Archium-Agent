"""Add scene_change_proposals table for auditable AI edit proposals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_scene_change_proposals"
down_revision: str | None = "019_presentation_manuscripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "scene_change_proposals" not in tables:
        op.create_table(
            "scene_change_proposals",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=False),
            sa.Column("slide_id", sa.Uuid(), nullable=False),
            sa.Column("base_revision_id", sa.Uuid(), nullable=True),
            sa.Column("base_scene_id", sa.Uuid(), nullable=False),
            sa.Column("proposed_scene_id", sa.Uuid(), nullable=False),
            sa.Column("base_scene_hash", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["base_scene_id"], ["render_scenes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["proposed_scene_id"], ["render_scenes.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_scene_change_proposals_slide_id",
            "scene_change_proposals",
            ["slide_id"],
        )
        op.create_index(
            "ix_scene_change_proposals_presentation_id",
            "scene_change_proposals",
            ["presentation_id"],
        )
        op.create_index(
            "ix_scene_change_proposals_status",
            "scene_change_proposals",
            ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "scene_change_proposals" in set(inspector.get_table_names()):
        op.drop_table("scene_change_proposals")
