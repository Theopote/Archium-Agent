"""Add approval_hash to deliverable_plans (WF-006 / MS-005).

Revision ID: 061_deliverable_plan_approval_hash
Revises: 060_organizations
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "061_deliverable_plan_approval_hash"
down_revision: str | None = "060_organizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deliverable_plans" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("deliverable_plans")}
    if "approval_hash" not in columns:
        op.add_column(
            "deliverable_plans",
            sa.Column("approval_hash", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deliverable_plans" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("deliverable_plans")}
    if "approval_hash" in columns:
        op.drop_column("deliverable_plans", "approval_hash")
