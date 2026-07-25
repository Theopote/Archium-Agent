"""Add nullable mission_id on visual_concept_briefs for pre-mission viz loop."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "049_visual_brief_optional_mission"
down_revision: str | None = "048_knowledge_state_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "visual_concept_briefs" not in tables:
        return
    with op.batch_alter_table("visual_concept_briefs") as batch:
        batch.alter_column(
            "mission_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "visual_concept_briefs" not in tables:
        return
    # Pre-mission briefs cannot survive NOT NULL; leave nullable if rows exist.
    with op.batch_alter_table("visual_concept_briefs") as batch:
        batch.alter_column(
            "mission_id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=True,
        )
