"""Initial database schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are created via init_database() for SQLite dev workflow.
    # This revision documents the baseline schema for Alembic tracking.
    pass


def downgrade() -> None:
    pass
