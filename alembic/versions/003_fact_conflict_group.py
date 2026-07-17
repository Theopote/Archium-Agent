"""Add conflict_group column to project_facts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_fact_conflict_group"
down_revision: Union[str, None] = "002_lineage_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "project_facts" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("project_facts")}
    if "conflict_group" in columns:
        return

    with op.batch_alter_table("project_facts") as batch:
        batch.add_column(sa.Column("conflict_group", sa.String(length=100), nullable=True))


def downgrade() -> None:
    pass
