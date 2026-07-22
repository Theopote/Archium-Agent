"""Add ElementCommentScope columns to element_comments."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032_element_comment_scope"
down_revision: str | None = "031_element_comment_scene_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("element_comments")}
    if "scope" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("scope", sa.String(length=40), nullable=False, server_default="node"),
        )
    if "scope_node_ids" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("scope_node_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )
    if "region_bbox" not in columns:
        op.add_column(
            "element_comments",
            sa.Column("region_bbox", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "element_comments" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("element_comments")}
    if "region_bbox" in columns:
        op.drop_column("element_comments", "region_bbox")
    if "scope_node_ids" in columns:
        op.drop_column("element_comments", "scope_node_ids")
    if "scope" in columns:
        op.drop_column("element_comments", "scope")
