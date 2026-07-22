"""Persist TemplateUsageBrief versions and bind ArtDirection pointers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "033_template_usage_briefs"
down_revision: str | None = "032_element_comment_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "template_usage_briefs" not in tables:
        op.create_table(
            "template_usage_briefs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("template_id", sa.String(length=80), nullable=False),
            sa.Column("template_name", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("project_id", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_template_usage_briefs_template_id",
            "template_usage_briefs",
            ["template_id"],
        )
        op.create_index(
            "ix_template_usage_briefs_project_id",
            "template_usage_briefs",
            ["project_id"],
        )

    if "art_directions" in tables:
        columns = {col["name"] for col in inspector.get_columns("art_directions")}
        if "template_usage_brief_id" not in columns:
            op.add_column(
                "art_directions",
                sa.Column("template_usage_brief_id", sa.Uuid(), nullable=True),
            )
        if "template_usage_brief_version" not in columns:
            op.add_column(
                "art_directions",
                sa.Column("template_usage_brief_version", sa.Integer(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "art_directions" in tables:
        columns = {col["name"] for col in inspector.get_columns("art_directions")}
        if "template_usage_brief_version" in columns:
            op.drop_column("art_directions", "template_usage_brief_version")
        if "template_usage_brief_id" in columns:
            op.drop_column("art_directions", "template_usage_brief_id")

    if "template_usage_briefs" in tables:
        op.drop_index(
            "ix_template_usage_briefs_project_id",
            table_name="template_usage_briefs",
        )
        op.drop_index(
            "ix_template_usage_briefs_template_id",
            table_name="template_usage_briefs",
        )
        op.drop_table("template_usage_briefs")
