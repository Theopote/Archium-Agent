"""Add outline_plans.page_asset_bindings for explicit page material bindings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_outline_page_asset_bindings"
down_revision: str | None = "023_outline_page_intents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_asset_bindings" not in columns:
        op.add_column(
            "outline_plans",
            sa.Column("page_asset_bindings", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_asset_bindings" in columns:
        op.drop_column("outline_plans", "page_asset_bindings")
