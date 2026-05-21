"""plagiarism_reports: add ban_threshold column

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = '4b75f732e6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('plagiarism_reports', sa.Column('ban_threshold', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('plagiarism_reports', 'ban_threshold')
