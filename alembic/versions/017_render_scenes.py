"""Add render_scenes table for unified visual scene persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_render_scenes"
down_revision: str | None = "016_reference_style_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "render_scenes" not in tables:
        op.create_table(
            "render_scenes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slide_id", sa.Uuid(), nullable=False),
            sa.Column("layout_plan_id", sa.Uuid(), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("scene_hash", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_render_scenes_slide_id", "render_scenes", ["slide_id"])
        op.create_index(
            "ix_render_scenes_layout_plan_id",
            "render_scenes",
            ["layout_plan_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "render_scenes" in set(inspector.get_table_names()):
        op.drop_table("render_scenes")
