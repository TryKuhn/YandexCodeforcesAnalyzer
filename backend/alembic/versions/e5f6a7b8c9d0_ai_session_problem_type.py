"""ai session: add problem_type column

Revision ID: e5f6a7b8c9d0
Revises: 579596ae2e6a
Create Date: 2026-06-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "579596ae2e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_sessions",
        sa.Column(
            "problem_type",
            sa.String(16),
            nullable=False,
            server_default="regular",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_sessions", "problem_type")
