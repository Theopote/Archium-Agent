"""Add lineage columns for briefs, storylines, slides and entity_revisions table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_lineage_artifacts"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _add_lineage_columns(
    table: str,
    *,
    default_logical_key: str,
) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, table):
        return

    columns = _column_names(inspector, table)
    if "lineage_id" in columns and "logical_key" in columns:
        return

    with op.batch_alter_table(table) as batch:
        if "lineage_id" not in columns:
            batch.add_column(sa.Column("lineage_id", sa.Uuid(), nullable=True))
        if "logical_key" not in columns:
            batch.add_column(sa.Column("logical_key", sa.String(length=200), nullable=True))

    op.execute(sa.text(f"UPDATE {table} SET lineage_id = id WHERE lineage_id IS NULL"))
    op.execute(
        sa.text(
            f"UPDATE {table} SET logical_key = :logical_key WHERE logical_key IS NULL"
        ).bindparams(logical_key=default_logical_key)
    )

    with op.batch_alter_table(table) as batch:
        batch.alter_column("lineage_id", nullable=False)
        batch.alter_column("logical_key", nullable=False)


def _ensure_entity_revisions_table() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "entity_revisions"):
        return

    if _table_exists(inspector, "slide_revisions"):
        with op.batch_alter_table("slide_revisions") as batch:
            batch.alter_column("slide_id", new_column_name="entity_id")
        op.rename_table("slide_revisions", "entity_revisions")
        inspector = sa.inspect(bind)

    columns = _column_names(inspector, "entity_revisions") if _table_exists(inspector, "entity_revisions") else set()
    if not columns:
        op.create_table(
            "entity_revisions",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False, server_default="slide"),
            sa.Column("entity_id", sa.Uuid(), nullable=True),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=True),
            sa.Column("revision_number", sa.Integer(), nullable=False),
            sa.Column("change_source", sa.String(length=40), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("actor", sa.String(length=200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_entity_revisions_lineage_id", "entity_revisions", ["lineage_id"])
        return

    with op.batch_alter_table("entity_revisions") as batch:
        if "entity_type" not in columns:
            batch.add_column(
                sa.Column("entity_type", sa.String(length=40), nullable=False, server_default="slide")
            )
        if "entity_id" not in columns and "slide_id" in columns:
            batch.alter_column("slide_id", new_column_name="entity_id")
        if "lineage_id" not in columns:
            batch.add_column(sa.Column("lineage_id", sa.Uuid(), nullable=True))
            op.execute(sa.text("UPDATE entity_revisions SET lineage_id = entity_id WHERE lineage_id IS NULL"))
            batch.alter_column("lineage_id", nullable=False)


def upgrade() -> None:
    _add_lineage_columns("presentation_briefs", default_logical_key="presentation-brief")
    _add_lineage_columns("storylines", default_logical_key="presentation-storyline")
    _add_lineage_columns("slides", default_logical_key="slide")
    _ensure_entity_revisions_table()


def downgrade() -> None:
    pass
