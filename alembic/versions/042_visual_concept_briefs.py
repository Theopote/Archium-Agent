"""Add visual_concept_briefs for Vision Engine concept-direction visuals."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042_visual_concept_briefs"
down_revision: str | None = "041_concept_directions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "visual_concept_briefs" in tables:
        return
    op.create_table(
        "visual_concept_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("concept_direction_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("composition_intent", sa.Text(), nullable=False),
        sa.Column("atmosphere", sa.Text(), nullable=False),
        sa.Column("diagram_intent", sa.Text(), nullable=False),
        sa.Column("image_type", sa.String(length=50), nullable=False),
        sa.Column("style_preset", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("elements", sa.JSON(), nullable=False),
        sa.Column("avoid", sa.JSON(), nullable=False),
        sa.Column("compiled_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("image_path", sa.String(length=2000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["project_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["concept_direction_id"], ["concept_directions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_visual_concept_briefs_project_id", "visual_concept_briefs", ["project_id"]
    )
    op.create_index(
        "ix_visual_concept_briefs_mission_id", "visual_concept_briefs", ["mission_id"]
    )
    op.create_index(
        "ix_visual_concept_briefs_direction_id",
        "visual_concept_briefs",
        ["concept_direction_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "visual_concept_briefs" not in tables:
        return
    op.drop_index(
        "ix_visual_concept_briefs_direction_id", table_name="visual_concept_briefs"
    )
    op.drop_index(
        "ix_visual_concept_briefs_mission_id", table_name="visual_concept_briefs"
    )
    op.drop_index(
        "ix_visual_concept_briefs_project_id", table_name="visual_concept_briefs"
    )
    op.drop_table("visual_concept_briefs")
