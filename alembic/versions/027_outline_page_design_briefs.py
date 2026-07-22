"""Add outline_plans.page_design_briefs for per-page SlideDesignBrief."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_outline_page_design_briefs"
down_revision: str | None = "026_outline_approval_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_design_briefs" not in columns:
        op.add_column(
            "outline_plans",
            sa.Column("page_design_briefs", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "outline_plans" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("outline_plans")}
    if "page_design_briefs" in columns:
        op.drop_column("outline_plans", "page_design_briefs")
