"""Add delivery_records.round_trip_report_json for export QA persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_delivery_round_trip_report"
down_revision: str | None = "027_outline_page_design_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "delivery_records" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("delivery_records")}
    if "round_trip_report_json" not in columns:
        op.add_column(
            "delivery_records",
            sa.Column("round_trip_report_json", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "delivery_records" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("delivery_records")}
    if "round_trip_report_json" in columns:
        op.drop_column("delivery_records", "round_trip_report_json")
