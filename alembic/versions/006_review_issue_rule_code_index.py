"""Add indexes on review_issues.rule_code for analytics queries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_review_issue_rule_code_index"
down_revision: Union[str, None] = "005_review_issue_rule_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_issues" not in inspector.get_table_names():
        return

    existing = {index["name"] for index in inspector.get_indexes("review_issues")}
    if "ix_review_issues_rule_code" not in existing:
        op.create_index("ix_review_issues_rule_code", "review_issues", ["rule_code"])
    if "ix_review_issues_presentation_rule_code" not in existing:
        op.create_index(
            "ix_review_issues_presentation_rule_code",
            "review_issues",
            ["presentation_id", "rule_code"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "review_issues" not in inspector.get_table_names():
        return

    existing = {index["name"] for index in inspector.get_indexes("review_issues")}
    if "ix_review_issues_presentation_rule_code" in existing:
        op.drop_index("ix_review_issues_presentation_rule_code", table_name="review_issues")
    if "ix_review_issues_rule_code" in existing:
        op.drop_index("ix_review_issues_rule_code", table_name="review_issues")
