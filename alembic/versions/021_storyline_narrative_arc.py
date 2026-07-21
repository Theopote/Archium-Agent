"""Add storylines.narrative_arc JSON column for formal narrative arc."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_storyline_narrative_arc"
down_revision: str | None = "020_scene_change_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "storylines" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("storylines")}
    if "narrative_arc" not in columns:
        op.add_column(
            "storylines",
            sa.Column("narrative_arc", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "storylines" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("storylines")}
    if "narrative_arc" in columns:
        op.drop_column("storylines", "narrative_arc")
