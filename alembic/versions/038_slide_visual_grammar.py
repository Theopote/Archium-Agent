"""Add page_archetype and required_evidence_slots to slides (VG-002).

Revision ID: 038_slide_visual_grammar
Revises: 037_fact_alternate_values
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "038_slide_visual_grammar"
down_revision: str | None = "037_fact_alternate_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "slides" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("slides")}
    with op.batch_alter_table("slides") as batch:
        if "page_archetype" not in columns:
            batch.add_column(sa.Column("page_archetype", sa.String(length=50), nullable=True))
        if "required_evidence_slots" not in columns:
            batch.add_column(
                sa.Column(
                    "required_evidence_slots",
                    sa.JSON(),
                    nullable=False,
                    server_default="[]",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "slides" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("slides")}
    with op.batch_alter_table("slides") as batch:
        if "required_evidence_slots" in columns:
            batch.drop_column("required_evidence_slots")
        if "page_archetype" in columns:
            batch.drop_column("page_archetype")
