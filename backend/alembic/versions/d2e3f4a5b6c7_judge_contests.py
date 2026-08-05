"""judge contests

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "judge_contests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scoring", sa.String(8), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("freeze_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "judge_contest_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contest_id",
            sa.Integer(),
            sa.ForeignKey("judge_contests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "problem_id",
            sa.Integer(),
            sa.ForeignKey("judge_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("max_points", sa.Float(), nullable=False),
        sa.UniqueConstraint("contest_id", "position"),
        sa.UniqueConstraint("contest_id", "problem_id"),
    )
    op.create_table(
        "judge_contest_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contest_id",
            sa.Integer(),
            sa.ForeignKey("judge_contests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("contest_id", "user_id"),
    )
    op.add_column(
        "judge_submissions", sa.Column("contest_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_judge_submissions_contest_id"), "judge_submissions", ["contest_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_judge_submissions_contest_id"), table_name="judge_submissions"
    )
    op.drop_column("judge_submissions", "contest_id")
    op.drop_table("judge_contest_participants")
    op.drop_table("judge_contest_problems")
    op.drop_table("judge_contests")
