"""ai session extensions: problem_settings, solution_meta, examples

Revision ID: b2c3d4e5f6a7
Revises: 1644f4a001ec
Create Date: 2026-05-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "1644f4a001ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_sessions", sa.Column("problem_settings", sa.JSON(), nullable=True)
    )
    op.add_column("ai_sessions", sa.Column("solution_meta", sa.JSON(), nullable=True))
    op.add_column("ai_sessions", sa.Column("examples", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_sessions", "examples")
    op.drop_column("ai_sessions", "solution_meta")
    op.drop_column("ai_sessions", "problem_settings")
