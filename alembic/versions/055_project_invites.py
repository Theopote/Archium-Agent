"""Add project_invites table (Phase N.2.2)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "055_project_invites"
down_revision: str | None = "054_background_jobs_project_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "project_invites" not in tables:
        op.create_table(
            "project_invites",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("role", sa.String(length=40), nullable=False, server_default="reviewer"),
            sa.Column(
                "created_by", sa.String(length=200), nullable=False, server_default="local-user"
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("label", sa.String(length=200), nullable=False, server_default=""),
        )
        op.create_unique_constraint("uq_project_invites_code", "project_invites", ["code"])
        op.create_index("ix_project_invites_project_id", "project_invites", ["project_id"])
        op.create_index("ix_project_invites_code", "project_invites", ["code"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "project_invites" in tables:
        op.drop_table("project_invites")
