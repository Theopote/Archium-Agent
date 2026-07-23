"""Initial database schema.

Creates the SQLAlchemy metadata baseline so a cold ``alembic upgrade head``
works without a prior ``create_all`` (DB-002). Later revisions remain
idempotent via table/column existence checks where they add objects that may
already exist after this baseline.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import archium.infrastructure.database.models  # noqa: F401
    from archium.infrastructure.database.base import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    import archium.infrastructure.database.models  # noqa: F401
    from archium.infrastructure.database.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
