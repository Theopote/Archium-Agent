"""Add idea_seed JSON on exploration_sessions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044_idea_seed"
down_revision: str | None = "043_exploration_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "exploration_sessions" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("exploration_sessions")}
    if "idea_seed" not in columns:
        with op.batch_alter_table("exploration_sessions") as batch:
            batch.add_column(sa.Column("idea_seed", sa.JSON(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, idea_text FROM exploration_sessions
            WHERE idea_seed IS NULL
            """
        )
    ).fetchall()
    for session_id, idea_text in rows:
        raw = (idea_text or "").strip() or "legacy"
        seed = {
            "raw_input": raw,
            "theme": "",
            "inspiration": "",
            "keywords": [],
            "imagination_level": "open",
            "source": "legacy_backfill",
        }
        connection.execute(
            sa.text(
                """
                UPDATE exploration_sessions
                SET idea_seed = :seed
                WHERE id = :id
                """
            ),
            {"id": str(session_id), "seed": seed},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "exploration_sessions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("exploration_sessions")}
    if "idea_seed" in columns:
        with op.batch_alter_table("exploration_sessions") as batch:
            batch.drop_column("idea_seed")
