"""Add visual composition tables and slide composition foreign keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_visual_composition"
down_revision: str | None = "010_planning_session_decouple"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "design_systems" not in tables:
        op.create_table(
            "design_systems",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="approved"),
            sa.Column("source_type", sa.String(length=30), nullable=False, server_default="builtin"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_design_systems_name", "design_systems", ["name"])
        op.create_index(
            "ix_design_systems_approval_status", "design_systems", ["approval_status"]
        )

    if "art_directions" not in tables:
        op.create_table(
            "art_directions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=True),
            sa.Column("deliverable_id", sa.String(length=200), nullable=True),
            sa.Column("design_system_id", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["presentation_id"], ["presentations.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_art_directions_project_id", "art_directions", ["project_id"])
        op.create_index(
            "ix_art_directions_presentation_id", "art_directions", ["presentation_id"]
        )
        op.create_index(
            "ix_art_directions_approval_status", "art_directions", ["approval_status"]
        )

    if "visual_intents" not in tables:
        op.create_table(
            "visual_intents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slide_id", sa.Uuid(), nullable=False),
            sa.Column("presentation_id", sa.Uuid(), nullable=True),
            sa.Column("art_direction_id", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["presentation_id"], ["presentations.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_visual_intents_slide_id", "visual_intents", ["slide_id"])
        op.create_index(
            "ix_visual_intents_presentation_id", "visual_intents", ["presentation_id"]
        )

    if "layout_plans" not in tables:
        op.create_table(
            "layout_plans",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slide_id", sa.Uuid(), nullable=False),
            sa.Column("design_system_id", sa.Uuid(), nullable=False),
            sa.Column("visual_intent_id", sa.Uuid(), nullable=False),
            sa.Column("layout_family", sa.String(length=50), nullable=False),
            sa.Column("layout_variant", sa.String(length=80), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "validation_status", sa.String(length=30), nullable=False, server_default="pending"
            ),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["slide_id"], ["slides.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_layout_plans_slide_id", "layout_plans", ["slide_id"])
        op.create_index(
            "ix_layout_plans_visual_intent_id", "layout_plans", ["visual_intent_id"]
        )
        op.create_index("ix_layout_plans_layout_family", "layout_plans", ["layout_family"])

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        with op.batch_alter_table("slides") as batch:
            if "visual_intent_id" not in columns:
                batch.add_column(sa.Column("visual_intent_id", sa.Uuid(), nullable=True))
            if "layout_plan_id" not in columns:
                batch.add_column(sa.Column("layout_plan_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "slides" in tables:
        columns = {col["name"] for col in inspector.get_columns("slides")}
        with op.batch_alter_table("slides") as batch:
            if "layout_plan_id" in columns:
                batch.drop_column("layout_plan_id")
            if "visual_intent_id" in columns:
                batch.drop_column("visual_intent_id")

    for table in ("layout_plans", "visual_intents", "art_directions", "design_systems"):
        if table in tables:
            op.drop_table(table)
