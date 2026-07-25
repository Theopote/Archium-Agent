"""Add presentation_intent on briefs; slide_role + visual_strategy on slides."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "052_presentation_intent_slide_role"
down_revision: str | None = "051_concept_spatial_design_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "presentation_briefs" in tables:
        columns = {col["name"] for col in inspector.get_columns("presentation_briefs")}
        with op.batch_alter_table("presentation_briefs") as batch:
            if "presentation_intent" not in columns:
                batch.add_column(sa.Column("presentation_intent", sa.JSON(), nullable=True))

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        with op.batch_alter_table("slides") as batch:
            if "slide_role" not in columns:
                batch.add_column(sa.Column("slide_role", sa.String(length=40), nullable=True))
            if "visual_strategy" not in columns:
                batch.add_column(sa.Column("visual_strategy", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        with op.batch_alter_table("slides") as batch:
            if "visual_strategy" in columns:
                batch.drop_column("visual_strategy")
            if "slide_role" in columns:
                batch.drop_column("slide_role")

    if "presentation_briefs" in tables:
        columns = {col["name"] for col in inspector.get_columns("presentation_briefs")}
        with op.batch_alter_table("presentation_briefs") as batch:
            if "presentation_intent" in columns:
                batch.drop_column("presentation_intent")
