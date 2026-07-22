"""Add scene version binding columns to element_comments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_element_comment_scene_binding"
down_revision: str | None = "030_theme_change_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("element_comments")}
    if "scene_revision_id" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("scene_revision_id", sa.Uuid(), nullable=True),
        )
    if "scene_hash" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("scene_hash", sa.String(length=64), nullable=False, server_default=""),
        )
    if "node_snapshot_json" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("node_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("element_comments")}
    if "ix_element_comments_scene_revision_id" not in indexes:
        op.create_index(
            "ix_element_comments_scene_revision_id",
            "element_comments",
            ["scene_revision_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" not in tables:
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("element_comments")}
    if "ix_element_comments_scene_revision_id" in indexes:
        op.drop_index(
            "ix_element_comments_scene_revision_id",
            table_name="element_comments",
        )

    columns = {col["name"] for col in inspector.get_columns("element_comments")}
    if "node_snapshot_json" in columns:
        op.drop_column("element_comments", "node_snapshot_json")
    if "scene_hash" in columns:
        op.drop_column("element_comments", "scene_hash")
    if "scene_revision_id" in columns:
        op.drop_column("element_comments", "scene_revision_id")
