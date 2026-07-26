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
    if "mission_id" in columns:
        return
    op.add_column(
        "presentations",
        sa.Column("mission_id", sa.Uuid(), nullable=True),
    )
    if "project_missions" in tables:
        op.create_foreign_key(
            "fk_presentations_mission_id",
            "presentations",
            "project_missions",
            ["mission_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_presentations_mission_id",
        "presentations",
        ["mission_id"],
    )


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
    if "ix_presentations_mission_id" in indexes:
        op.drop_index("ix_presentations_mission_id", table_name="presentations")
    fks = {fk["name"] for fk in inspector.get_foreign_keys("presentations")}
    if "fk_presentations_mission_id" in fks:
        op.drop_constraint(
            "fk_presentations_mission_id",
            "presentations",
            type_="foreignkey",
        )
    op.drop_column("presentations", "mission_id")
