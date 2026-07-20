"""Add renovation_issue_maps table and projects.current_renovation_issue_map_id."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_renovation_issue_maps"
down_revision: str | None = "014_cultural_narrative_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "renovation_issue_maps" not in tables:
        op.create_table(
            "renovation_issue_maps",
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
                server_default="project-renovation-issue-map",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_renovation_issue_maps_project_id",
            "renovation_issue_maps",
            ["project_id"],
        )
        op.create_index(
            "ix_renovation_issue_maps_lineage_id",
            "renovation_issue_maps",
            ["lineage_id"],
        )

    project_columns = {col["name"] for col in inspector.get_columns("projects")}
    if "current_renovation_issue_map_id" not in project_columns:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.add_column(sa.Column("current_renovation_issue_map_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    project_columns = {col["name"] for col in inspector.get_columns("projects")}
    if "current_renovation_issue_map_id" in project_columns:
        with op.batch_alter_table("projects") as batch_op:
            batch_op.drop_column("current_renovation_issue_map_id")
    if "renovation_issue_maps" in inspector.get_table_names():
        op.drop_index("ix_renovation_issue_maps_lineage_id", table_name="renovation_issue_maps")
        op.drop_index("ix_renovation_issue_maps_project_id", table_name="renovation_issue_maps")
        op.drop_table("renovation_issue_maps")
