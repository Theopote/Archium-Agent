"""Add exploration_sessions; reparent concept_directions under exploration."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "043_exploration_sessions"
down_revision: str | None = "042_visual_concept_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "exploration_sessions" not in tables:
        op.create_table(
            "exploration_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("idea_text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("selected_direction_id", sa.Uuid(), nullable=True),
            sa.Column("mission_id", sa.Uuid(), nullable=True),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["mission_id"], ["project_missions.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_exploration_sessions_project_id",
            "exploration_sessions",
            ["project_id"],
        )
        op.create_index(
            "ix_exploration_sessions_status",
            "exploration_sessions",
            ["status"],
        )

    if "concept_directions" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    with op.batch_alter_table("concept_directions") as batch:
        if "exploration_session_id" not in columns:
            batch.add_column(sa.Column("exploration_session_id", sa.Uuid(), nullable=True))
        batch.alter_column("mission_id", existing_type=sa.Uuid(), nullable=True)

    connection = op.get_bind()
    now = datetime.now(UTC)
    rows = connection.execute(
        sa.text(
            """
            SELECT DISTINCT project_id, mission_id
            FROM concept_directions
            WHERE mission_id IS NOT NULL
              AND exploration_session_id IS NULL
            """
        )
    ).fetchall()
    for project_id, mission_id in rows:
        existing = connection.execute(
            sa.text(
                """
                SELECT id FROM exploration_sessions
                WHERE mission_id = :mission_id AND source = 'legacy_backfill'
                LIMIT 1
                """
            ),
            {"mission_id": str(mission_id)},
        ).fetchone()
        if existing:
            session_id = existing[0]
        else:
            session_id = uuid.uuid4()
            idea = connection.execute(
                sa.text(
                    """
                    SELECT COALESCE(NULLIF(TRIM(task_statement), ''), title, 'legacy')
                    FROM project_missions WHERE id = :mission_id
                    """
                ),
                {"mission_id": str(mission_id)},
            ).scalar()
            selected = connection.execute(
                sa.text(
                    """
                    SELECT id FROM concept_directions
                    WHERE mission_id = :mission_id AND status = 'selected'
                    ORDER BY updated_at DESC LIMIT 1
                    """
                ),
                {"mission_id": str(mission_id)},
            ).scalar()
            connection.execute(
                sa.text(
                    """
                    INSERT INTO exploration_sessions (
                        id, created_at, updated_at, project_id, idea_text, status,
                        selected_direction_id, mission_id, source
                    ) VALUES (
                        :id, :created_at, :updated_at, :project_id, :idea_text, :status,
                        :selected_direction_id, :mission_id, :source
                    )
                    """
                ),
                {
                    "id": str(session_id),
                    "created_at": now,
                    "updated_at": now,
                    "project_id": str(project_id),
                    "idea_text": idea or "legacy exploration",
                    "status": "committed",
                    "selected_direction_id": str(selected) if selected else None,
                    "mission_id": str(mission_id),
                    "source": "legacy_backfill",
                },
            )
        connection.execute(
            sa.text(
                """
                UPDATE concept_directions
                SET exploration_session_id = :session_id
                WHERE mission_id = :mission_id AND exploration_session_id IS NULL
                """
            ),
            {"session_id": str(session_id), "mission_id": str(mission_id)},
        )

    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("concept_directions")}
    if "ix_concept_directions_exploration_session_id" not in indexes:
        op.create_index(
            "ix_concept_directions_exploration_session_id",
            "concept_directions",
            ["exploration_session_id"],
        )

    with op.batch_alter_table("concept_directions") as batch:
        batch.create_foreign_key(
            "fk_concept_directions_exploration_session_id",
            "exploration_sessions",
            ["exploration_session_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" in tables:
        columns = {col["name"] for col in inspector.get_columns("concept_directions")}
        indexes = {idx["name"] for idx in inspector.get_indexes("concept_directions")}
        with op.batch_alter_table("concept_directions") as batch:
            try:
                batch.drop_constraint(
                    "fk_concept_directions_exploration_session_id", type_="foreignkey"
                )
            except Exception:
                pass
            if "ix_concept_directions_exploration_session_id" in indexes:
                batch.drop_index("ix_concept_directions_exploration_session_id")
            if "exploration_session_id" in columns:
                batch.drop_column("exploration_session_id")
            batch.alter_column("mission_id", existing_type=sa.Uuid(), nullable=False)
    if "exploration_sessions" in tables:
        op.drop_index(
            "ix_exploration_sessions_status", table_name="exploration_sessions"
        )
        op.drop_index(
            "ix_exploration_sessions_project_id", table_name="exploration_sessions"
        )
        op.drop_table("exploration_sessions")
