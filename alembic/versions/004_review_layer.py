"""Add reviewer_layer column to review_issues."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_review_layer"
down_revision: Union[str, None] = "003_fact_conflict_group"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_issues" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("review_issues")}
    if "reviewer_layer" in columns:
        return

    with op.batch_alter_table("review_issues") as batch:
        batch.add_column(
            sa.Column(
                "reviewer_layer",
                sa.String(length=30),
                nullable=False,
                server_default="content",
            )
        )


def downgrade() -> None:
    pass
