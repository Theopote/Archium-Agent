"""Add concept_directions for design-iteration drafts under a mission."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "041_concept_directions"
down_revision: str | None = "040_artifact_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" in tables:
        return
    op.create_table(
        "concept_directions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("theme", sa.String(length=500), nullable=False),
        sa.Column("spatial_idea", sa.Text(), nullable=False),
        sa.Column("experience_focus", sa.Text(), nullable=False),
        sa.Column("differentiator", sa.Text(), nullable=False),
        sa.Column("open_questions_json", sa.JSON(), nullable=False),
        sa.Column("risks_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["project_missions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_concept_directions_project_id", "concept_directions", ["project_id"])
    op.create_index("ix_concept_directions_mission_id", "concept_directions", ["mission_id"])
    op.create_index("ix_concept_directions_status", "concept_directions", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "concept_directions" not in tables:
        return
    op.drop_index("ix_concept_directions_status", table_name="concept_directions")
    op.drop_index("ix_concept_directions_mission_id", table_name="concept_directions")
    op.drop_index("ix_concept_directions_project_id", table_name="concept_directions")
    op.drop_table("concept_directions")
