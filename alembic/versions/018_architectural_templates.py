"""Add architectural_templates table for Template Studio."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_architectural_templates"
down_revision: str | None = "017_render_scenes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "architectural_templates" not in tables:
        op.create_table(
            "architectural_templates",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=True),
            sa.Column("design_system_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source_pptx_path", sa.String(length=1000), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_architectural_templates_project_id",
            "architectural_templates",
            ["project_id"],
        )
        op.create_index(
            "ix_architectural_templates_status",
            "architectural_templates",
            ["status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "architectural_templates" in set(inspector.get_table_names()):
        op.drop_table("architectural_templates")
