"""Add deck/slide delivery status columns for partial-failure delivery."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_deck_delivery_status"
down_revision: str | None = "021_storyline_narrative_arc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "presentations" in tables:
        columns = {col["name"] for col in inspector.get_columns("presentations")}
        if "delivery_status" not in columns:
            op.add_column(
                "presentations",
                sa.Column(
                    "delivery_status",
                    sa.String(length=40),
                    nullable=False,
                    server_default="ready",
                ),
            )

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        if "delivery_status" not in columns:
            op.add_column(
                "slides",
                sa.Column(
                    "delivery_status",
                    sa.String(length=40),
                    nullable=False,
                    server_default="ready",
                ),
            )
        if "delivery_detail" not in columns:
            op.add_column(
                "slides",
                sa.Column("delivery_detail", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        if "delivery_detail" in columns:
            op.drop_column("slides", "delivery_detail")
        if "delivery_status" in columns:
            op.drop_column("slides", "delivery_status")

    if "presentations" in tables:
        columns = {col["name"] for col in inspector.get_columns("presentations")}
        if "delivery_status" in columns:
            op.drop_column("presentations", "delivery_status")
