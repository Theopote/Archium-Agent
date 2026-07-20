"""Add reference_style_profiles table and projects.current_reference_style_profile_id."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_reference_style_profiles"
down_revision: str | None = "015_renovation_issue_maps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reference_style_profiles" not in tables:
        op.create_table(
            "reference_style_profiles",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column(
                "logical_key",
                sa.String(length=200),
                nullable=False,
                server_default="project-reference-style-profile",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_reference_style_profiles_project_id",
            "reference_style_profiles",
            ["project_id"],
        )
        op.create_index(
            "ix_reference_style_profiles_lineage_id",
            "reference_style_profiles",
            ["lineage_id"],
        )

    project_columns = {col["name"] for col in inspector.get_columns("projects")}
    if "current_reference_style_profile_id" not in project_columns:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.add_column(sa.Column("current_reference_style_profile_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    project_columns = {col["name"] for col in inspector.get_columns("projects")}
    if "current_reference_style_profile_id" in project_columns:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.drop_column("current_reference_style_profile_id")
    if "reference_style_profiles" in inspector.get_table_names():
        op.drop_index("ix_reference_style_profiles_lineage_id", table_name="reference_style_profiles")
        op.drop_index("ix_reference_style_profiles_project_id", table_name="reference_style_profiles")
        op.drop_table("reference_style_profiles")
