"""Add delivery_records for persisted export history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_delivery_records"
down_revision: str | None = "024_outline_page_asset_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "delivery_records" in tables:
        return
    op.create_table(
        "delivery_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("presentation_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=True),
        sa.Column("format", sa.String(length=40), nullable=False),
        sa.Column("file_uri", sa.String(length=2000), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("qa_status", sa.String(length=40), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["presentation_id"], ["presentations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_records_project_id", "delivery_records", ["project_id"])
    op.create_index(
        "ix_delivery_records_presentation_id", "delivery_records", ["presentation_id"]
    )
    op.create_index("ix_delivery_records_exported_at", "delivery_records", ["exported_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "delivery_records" not in tables:
        return
    op.drop_index("ix_delivery_records_exported_at", table_name="delivery_records")
    op.drop_index("ix_delivery_records_presentation_id", table_name="delivery_records")
    op.drop_index("ix_delivery_records_project_id", table_name="delivery_records")
    op.drop_table("delivery_records")
