"""Add background job idempotency_key and cancel_requested (APP-029)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "063_background_job_idempotency_cancel"
down_revision: str | None = "062_slide_evidence_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "background_jobs" not in set(inspector.get_table_names()):
        return
    columns = {col["name"] for col in inspector.get_columns("background_jobs")}
    if "idempotency_key" not in columns:
        op.add_column(
            "background_jobs",
            sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        )
    if "cancel_requested" not in columns:
        op.add_column(
            "background_jobs",
            sa.Column(
                "cancel_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("background_jobs")}
    if "uq_background_jobs_project_idempotency" not in indexes:
        op.create_index(
            "uq_background_jobs_project_idempotency",
            "background_jobs",
            ["project_id", "idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "background_jobs" not in set(inspector.get_table_names()):
        return
    indexes = {idx["name"] for idx in inspector.get_indexes("background_jobs")}
    if "uq_background_jobs_project_idempotency" in indexes:
        op.drop_index(
            "uq_background_jobs_project_idempotency",
            table_name="background_jobs",
        )
    columns = {col["name"] for col in inspector.get_columns("background_jobs")}
    if "cancel_requested" in columns:
        op.drop_column("background_jobs", "cancel_requested")
    if "idempotency_key" in columns:
        op.drop_column("background_jobs", "idempotency_key")
