"""Add approval hash to project missions.

Revision ID: 035_project_mission_approval_hash
Revises: 034_project_mission_narrative_mode
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "035_project_mission_approval_hash"
down_revision: str | None = "034_project_mission_narrative_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_missions", sa.Column("approval_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("project_missions", "approval_hash")
