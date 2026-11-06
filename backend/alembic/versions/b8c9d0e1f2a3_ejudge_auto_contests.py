"""ejudge contests created automatically for publications

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ejudge_auto_contests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_key", sa.String(512), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("host_key", "contest_id", name="uq_ejudge_auto_contests_host_contest"),
    )
    op.create_index("ix_ejudge_auto_contests_host_key", "ejudge_auto_contests", ["host_key"])


def downgrade() -> None:
    op.drop_index("ix_ejudge_auto_contests_host_key", table_name="ejudge_auto_contests")
    op.drop_table("ejudge_auto_contests")
