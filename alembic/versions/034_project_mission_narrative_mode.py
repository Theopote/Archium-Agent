"""Persist the mission-level architectural narrative mode."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034_project_mission_narrative_mode"
down_revision: str | None = "033_template_usage_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_missions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("project_missions")}
    if "narrative_mode" not in columns:
        op.add_column(
            "project_missions",
            sa.Column("narrative_mode", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_missions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("project_missions")}
    if "narrative_mode" in columns:
        op.drop_column("project_missions", "narrative_mode")

