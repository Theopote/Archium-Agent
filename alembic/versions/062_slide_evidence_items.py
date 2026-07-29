"""Add evidence_items JSON column on slides."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "062_slide_evidence_items"
down_revision: str | None = "061_deliverable_plan_approval_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "slides" not in set(inspector.get_table_names()):
        return
    columns = {col["name"] for col in inspector.get_columns("slides")}
    if "evidence_items" in columns:
        return
    with op.batch_alter_table("slides") as batch:
        batch.add_column(sa.Column("evidence_items", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "slides" not in set(inspector.get_table_names()):
        return
    columns = {col["name"] for col in inspector.get_columns("slides")}
    if "evidence_items" not in columns:
        return
    with op.batch_alter_table("slides") as batch:
        batch.drop_column("evidence_items")
