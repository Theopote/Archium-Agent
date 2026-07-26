"""Add organizations table + projects.organization_id (DOM-032 / Topic 08)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "060_organizations"
down_revision: str | None = "059_presentation_mission_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("name", sa.String(length=300), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=True),
            sa.Column(
                "display_name",
                sa.String(length=300),
                nullable=False,
                server_default="",
            ),
        )
        op.create_index(
            "ix_organizations_slug",
            "organizations",
            ["slug"],
            unique=True,
        )

    if "projects" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("projects")}
    if "organization_id" in columns:
        return
    op.add_column(
        "projects",
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_organization_id",
        "projects",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_projects_organization_id",
        "projects",
        ["organization_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "projects" in tables:
        columns = {col["name"] for col in inspector.get_columns("projects")}
        if "organization_id" in columns:
            indexes = {idx["name"] for idx in inspector.get_indexes("projects")}
            if "ix_projects_organization_id" in indexes:
                op.drop_index(
                    "ix_projects_organization_id", table_name="projects"
                )
            fks = {fk["name"] for fk in inspector.get_foreign_keys("projects")}
            if "fk_projects_organization_id" in fks:
                op.drop_constraint(
                    "fk_projects_organization_id",
                    "projects",
                    type_="foreignkey",
                )
            op.drop_column("projects", "organization_id")

    if "organizations" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("organizations")}
        if "ix_organizations_slug" in indexes:
            op.drop_index("ix_organizations_slug", table_name="organizations")
        op.drop_table("organizations")
