"""Add structured concept direction fields for spatial/form/visual intent."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046_concept_direction_structure"
down_revision: str | None = "045_knowledge_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    with op.batch_alter_table("concept_directions") as batch:
        if "spatial_strategy" not in columns:
            batch.add_column(sa.Column("spatial_strategy", sa.Text(), nullable=False, server_default=""))
        if "formal_language" not in columns:
            batch.add_column(sa.Column("formal_language", sa.Text(), nullable=False, server_default=""))
        if "material_strategy" not in columns:
            batch.add_column(sa.Column("material_strategy", sa.Text(), nullable=False, server_default=""))
        if "reference_dna" not in columns:
            batch.add_column(sa.Column("reference_dna", sa.JSON(), nullable=False, server_default="[]"))
        if "visual_prompt" not in columns:
            batch.add_column(sa.Column("visual_prompt", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("concept_directions")}
    with op.batch_alter_table("concept_directions") as batch:
        if "visual_prompt" in columns:
            batch.drop_column("visual_prompt")
        if "reference_dna" in columns:
            batch.drop_column("reference_dna")
        if "material_strategy" in columns:
            batch.drop_column("material_strategy")
        if "formal_language" in columns:
            batch.drop_column("formal_language")
        if "spatial_strategy" in columns:
            batch.drop_column("spatial_strategy")
