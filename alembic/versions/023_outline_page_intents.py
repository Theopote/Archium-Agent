"""Add outline_plans.page_intents for per-page Slide Intent Cards."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_outline_page_intents"
down_revision: str | None = "022_deck_delivery_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_intents" not in columns:
        op.add_column(
            "outline_plans",
            sa.Column("page_intents", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_intents" in columns:
        op.drop_column("outline_plans", "page_intents")
