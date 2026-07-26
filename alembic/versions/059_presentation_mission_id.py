"""Add presentations.mission_id for Mission↔Presentation lineage (MS-002 / Topic 07 L3)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "059_presentation_mission_id"
down_revision: str | None = "058_knowledge_graph_edges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "presentations" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("presentations")}
    indexes = {idx["name"] for idx in inspector.get_indexes("presentations")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("presentations")}
    need_column = "mission_id" not in columns
    need_fk = (
        "project_missions" in tables
        and "fk_presentations_mission_id" not in fks
    )
    need_index = "ix_presentations_mission_id" not in indexes
    if not (need_column or need_fk or need_index):
        return
    with op.batch_alter_table("presentations") as batch:
        if need_column:
            batch.add_column(sa.Column("mission_id", sa.Uuid(), nullable=True))
        if need_fk:
            batch.create_foreign_key(
                "fk_presentations_mission_id",
                "project_missions",
                ["mission_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if need_index:
            batch.create_index("ix_presentations_mission_id", ["mission_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "presentations" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("presentations")}
    if "mission_id" not in columns:
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("presentations")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("presentations")}
    with op.batch_alter_table("presentations") as batch:
        if "ix_presentations_mission_id" in indexes:
            batch.drop_index("ix_presentations_mission_id")
        if "fk_presentations_mission_id" in fks:
            batch.drop_constraint(
                "fk_presentations_mission_id",
                type_="foreignkey",
            )
        batch.drop_column("mission_id")
