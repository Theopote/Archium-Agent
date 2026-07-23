"""Add alternate_values to project_facts (KN-001).

Revision ID: 037_fact_alternate_values
Revises: 036_delivery_artifact_lineage
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "037_fact_alternate_values"
down_revision: str | None = "036_delivery_artifact_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_facts" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("project_facts")}
    if "alternate_values" in columns:
        return
    with op.batch_alter_table("project_facts") as batch:
        batch.add_column(
            sa.Column(
                "alternate_values",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_facts" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("project_facts")}
    if "alternate_values" not in columns:
        return
    with op.batch_alter_table("project_facts") as batch:
        batch.drop_column("alternate_values")
