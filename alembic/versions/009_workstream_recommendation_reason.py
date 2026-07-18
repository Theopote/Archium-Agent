"""Add recommendation_reason to workstreams."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_workstream_recommendation_reason"
down_revision: str | None = "008_project_mission_planning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "workstreams" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("workstreams")}
    if "recommendation_reason" not in columns:
        op.add_column(
            "workstreams",
            sa.Column(
                "recommendation_reason",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "workstreams" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("workstreams")}
    if "recommendation_reason" in columns:
        op.drop_column("workstreams", "recommendation_reason")
