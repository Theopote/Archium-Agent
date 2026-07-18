"""Add planning_sessions and make workflow_runs.presentation_id nullable."""

import json
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "010_planning_session_decouple"
down_revision: str | None = "009_workstream_recommendation_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "workflow_runs" in tables:
        columns = {col["name"]: col for col in inspector.get_columns("workflow_runs")}
        presentation_col = columns.get("presentation_id")
        if presentation_col is not None and presentation_col.get("nullable") is False:
            with op.batch_alter_table("workflow_runs") as batch:
                batch.alter_column(
                    "presentation_id",
                    existing_type=sa.Uuid(),
                    nullable=True,
                )

    if "planning_sessions" not in tables:
        op.create_table(
            "planning_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("current_mission_id", sa.Uuid(), nullable=True),
            sa.Column("workflow_run_id", sa.Uuid(), nullable=True),
            sa.Column("presentation_id", sa.Uuid(), nullable=True),
            sa.Column("user_task_description", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["current_mission_id"], ["project_missions.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["presentation_id"], ["presentations.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_planning_sessions_project_id", "planning_sessions", ["project_id"]
        )
        op.create_index(
            "ix_planning_sessions_workflow_run_id",
            "planning_sessions",
            ["workflow_run_id"],
        )
        op.create_index("ix_planning_sessions_status", "planning_sessions", ["status"])

    # Backfill sessions for existing planning workflow runs.
    tables = set(sa.inspect(bind).get_table_names())
    if "workflow_runs" not in tables or "planning_sessions" not in tables:
        return

    runs = bind.execute(
        sa.text(
            "SELECT id, project_id, status, state, created_at, updated_at "
            "FROM workflow_runs"
        )
    ).mappings()
    existing = {
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT workflow_run_id FROM planning_sessions "
                "WHERE workflow_run_id IS NOT NULL"
            )
        )
    }
    for run in runs:
        state = run["state"]
        if isinstance(state, str):
            try:
                state = json.loads(state)
            except json.JSONDecodeError:
                continue
        if not isinstance(state, dict):
            continue
        if state.get("workflow_kind") != "planning":
            continue
        if str(run["id"]) in existing:
            continue

        mission_id = state.get("mission_id")
        if not mission_id and isinstance(state.get("mission"), dict):
            mission_id = state["mission"].get("id")
        task = state.get("user_task_description") or ""
        status = _session_status_for_run(run["status"], state)

        bind.execute(
            sa.text(
                "INSERT INTO planning_sessions "
                "(id, project_id, status, current_mission_id, workflow_run_id, "
                "presentation_id, user_task_description, created_at, updated_at) "
                "VALUES (:id, :project_id, :status, :current_mission_id, :workflow_run_id, "
                "NULL, :user_task_description, :created_at, :updated_at)"
            ),
            {
                "id": str(uuid4()),
                "project_id": str(run["project_id"]),
                "status": status,
                "current_mission_id": str(mission_id) if mission_id else None,
                "workflow_run_id": str(run["id"]),
                "user_task_description": task,
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
            },
        )


def _session_status_for_run(run_status: str, state: dict) -> str:
    if run_status == "failed":
        return "failed"
    if run_status == "completed":
        return "ready"
    if run_status == "awaiting_review":
        gate = state.get("review_gate")
        if gate == "clarification":
            return "clarifying"
        if gate == "plan_approval":
            return "awaiting_approval"
    if run_status == "running":
        return "planning"
    return "draft"


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "planning_sessions" in tables:
        op.drop_index("ix_planning_sessions_status", table_name="planning_sessions")
        op.drop_index("ix_planning_sessions_workflow_run_id", table_name="planning_sessions")
        op.drop_index("ix_planning_sessions_project_id", table_name="planning_sessions")
        op.drop_table("planning_sessions")

    if "workflow_runs" in tables:
        null_count = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM workflow_runs WHERE presentation_id IS NULL"
            )
        ).scalar()
        if not null_count:
            with op.batch_alter_table("workflow_runs") as batch:
                batch.alter_column(
                    "presentation_id",
                    existing_type=sa.Uuid(),
                    nullable=False,
                )
