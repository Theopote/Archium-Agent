"""Add project origin mode and mission design_intent for concept exploration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039_project_origin_design_intent"
down_revision: str | None = "038_slide_visual_grammar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "origin_mode" not in columns:
            with op.batch_alter_table("projects") as batch:
                batch.add_column(
                    sa.Column(
                        "origin_mode",
                        sa.String(length=50),
                        nullable=False,
                        server_default="existing_project",
                    )
                )

    if "planning_sessions" in tables:
        columns = {column["name"] for column in inspector.get_columns("planning_sessions")}
        if "origin_mode" not in columns:
            with op.batch_alter_table("planning_sessions") as batch:
                batch.add_column(
                    sa.Column(
                        "origin_mode",
                        sa.String(length=50),
                        nullable=False,
                        server_default="existing_project",
                    )
                )

    if "project_missions" in tables:
        columns = {column["name"] for column in inspector.get_columns("project_missions")}
        if "design_intent" not in columns:
            with op.batch_alter_table("project_missions") as batch:
                batch.add_column(sa.Column("design_intent", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "project_missions" in tables:
        columns = {column["name"] for column in inspector.get_columns("project_missions")}
        if "design_intent" in columns:
            with op.batch_alter_table("project_missions") as batch:
                batch.drop_column("design_intent")

    if "planning_sessions" in tables:
        columns = {column["name"] for column in inspector.get_columns("planning_sessions")}
        if "origin_mode" in columns:
            with op.batch_alter_table("planning_sessions") as batch:
                batch.drop_column("origin_mode")

    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        if "origin_mode" in columns:
            with op.batch_alter_table("projects") as batch:
                batch.drop_column("origin_mode")
