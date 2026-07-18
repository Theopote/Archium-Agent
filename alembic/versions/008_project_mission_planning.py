"""Add project mission and adaptive planning tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_project_mission_planning"
down_revision: str | None = "007_visual_qa_reports_and_review_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.Inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "project_missions"):
        op.create_table(
            "project_missions",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column("logical_key", sa.String(length=200), nullable=False, server_default="project-mission"),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("task_statement", sa.Text(), nullable=False),
            sa.Column("task_natures", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("domains", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("intervention_scales", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("requested_service_depths", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("project_context", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_situation", sa.Text(), nullable=False, server_default=""),
            sa.Column("primary_problems", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("desired_changes", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("in_scope", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("out_of_scope", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("stakeholders", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("decision_context", sa.Text(), nullable=False, server_default=""),
            sa.Column("decisions_required", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("known_constraints", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("key_unknowns", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("research_questions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("design_question_summaries", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("evaluation_criteria", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("recommended_workstream_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("recommended_deliverable_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("uncertainty_level", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_missions_project_id", "project_missions", ["project_id"])
        op.create_index("ix_project_missions_lineage_id", "project_missions", ["lineage_id"])
        op.create_index("ix_project_missions_approval_status", "project_missions", ["approval_status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "knowledge_gaps"):
        op.create_table(
            "knowledge_gaps",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(length=50), nullable=False, server_default="other"),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("why_it_matters", sa.Text(), nullable=False),
            sa.Column("impact_if_unresolved", sa.Text(), nullable=False, server_default=""),
            sa.Column("resolution_methods", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("suggested_owner", sa.String(length=200), nullable=True),
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("resolution", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_knowledge_gaps_project_id", "knowledge_gaps", ["project_id"])
        op.create_index("ix_knowledge_gaps_mission_id", "knowledge_gaps", ["mission_id"])
        op.create_index("ix_knowledge_gaps_status", "knowledge_gaps", ["status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "project_assumptions"):
        op.create_table(
            "project_assumptions",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("scope_of_use", sa.Text(), nullable=False, server_default=""),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("risk_level", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="proposed"),
            sa.Column("related_gap_ids", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_assumptions_project_id", "project_assumptions", ["project_id"])
        op.create_index("ix_project_assumptions_mission_id", "project_assumptions", ["mission_id"])
        op.create_index("ix_project_assumptions_status", "project_assumptions", ["status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "clarifying_questions"):
        op.create_table(
            "clarifying_questions",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "knowledge_gap_id",
                sa.Uuid(),
                sa.ForeignKey("knowledge_gaps.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("why_asked", sa.Text(), nullable=False),
            sa.Column("answer_type", sa.String(length=30), nullable=False, server_default="text"),
            sa.Column("options", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("can_assume", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("suggested_assumption", sa.Text(), nullable=False, server_default=""),
            sa.Column("answer", sa.JSON(), nullable=True),
            sa.Column("answer_source", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_clarifying_questions_project_id", "clarifying_questions", ["project_id"])
        op.create_index("ix_clarifying_questions_mission_id", "clarifying_questions", ["mission_id"])
        op.create_index("ix_clarifying_questions_status", "clarifying_questions", ["status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "design_questions"):
        op.create_table(
            "design_questions",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("context", sa.Text(), nullable=False, server_default=""),
            sa.Column("related_problem", sa.Text(), nullable=False, server_default=""),
            sa.Column("constraints", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("desired_outcome", sa.Text(), nullable=False, server_default=""),
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_design_questions_project_id", "design_questions", ["project_id"])
        op.create_index("ix_design_questions_mission_id", "design_questions", ["mission_id"])
        op.create_index("ix_design_questions_status", "design_questions", ["status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "workstreams"):
        op.create_table(
            "workstreams",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("workstream_type", sa.String(length=50), nullable=False, server_default="other"),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("questions", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("inputs_required", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("activities", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("outputs", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("dependencies", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("blocking_gaps", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("priority", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("effort_level", sa.String(length=30), nullable=False, server_default="medium"),
            sa.Column("recommended", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="proposed"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_workstreams_project_id", "workstreams", ["project_id"])
        op.create_index("ix_workstreams_mission_id", "workstreams", ["mission_id"])
        op.create_index("ix_workstreams_lineage_id", "workstreams", ["lineage_id"])
        op.create_index("ix_workstreams_status", "workstreams", ["status"])

    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "deliverable_plans"):
        op.create_table(
            "deliverable_plans",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "mission_id",
                sa.Uuid(),
                sa.ForeignKey("project_missions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("lineage_id", sa.Uuid(), nullable=False),
            sa.Column("logical_key", sa.String(length=200), nullable=False, server_default="deliverable-plan"),
            sa.Column("deliverables", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("approval_status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_deliverable_plans_project_id", "deliverable_plans", ["project_id"])
        op.create_index("ix_deliverable_plans_mission_id", "deliverable_plans", ["mission_id"])
        op.create_index("ix_deliverable_plans_lineage_id", "deliverable_plans", ["lineage_id"])
        op.create_index("ix_deliverable_plans_approval_status", "deliverable_plans", ["approval_status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in (
        "deliverable_plans",
        "workstreams",
        "design_questions",
        "clarifying_questions",
        "project_assumptions",
        "knowledge_gaps",
        "project_missions",
    ):
        if _table_exists(inspector, table):
            op.drop_table(table)
