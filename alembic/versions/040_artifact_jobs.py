"""Add artifact_jobs for non-presentation deliverable generation lifecycle."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "040_artifact_jobs"
down_revision: str | None = "039_project_origin_design_intent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "artifact_jobs" in tables:
        return
    op.create_table(
        "artifact_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("deliverable_id", sa.String(length=100), nullable=False),
        sa.Column("deliverable_title", sa.String(length=500), nullable=False),
        sa.Column("deliverable_type", sa.String(length=50), nullable=False),
        sa.Column("request_kind", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("json_path", sa.String(length=2000), nullable=True),
        sa.Column("markdown_path", sa.String(length=2000), nullable=True),
        sa.Column("docx_path", sa.String(length=2000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["project_missions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifact_jobs_project_id", "artifact_jobs", ["project_id"])
    op.create_index("ix_artifact_jobs_mission_id", "artifact_jobs", ["mission_id"])
    op.create_index("ix_artifact_jobs_status", "artifact_jobs", ["status"])
    op.create_index(
        "ix_artifact_jobs_mission_deliverable",
        "artifact_jobs",
        ["mission_id", "deliverable_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "artifact_jobs" not in tables:
        return
    op.drop_index("ix_artifact_jobs_mission_deliverable", table_name="artifact_jobs")
    op.drop_index("ix_artifact_jobs_status", table_name="artifact_jobs")
    op.drop_index("ix_artifact_jobs_mission_id", table_name="artifact_jobs")
    op.drop_index("ix_artifact_jobs_project_id", table_name="artifact_jobs")
    op.drop_table("artifact_jobs")
