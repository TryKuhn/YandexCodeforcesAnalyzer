"""judge tables

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-08-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "judge_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("time_limit_ms", sa.Integer(), nullable=False),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=False),
        sa.Column("checker_sha", sa.String(64), nullable=True),
        sa.Column("validator_sha", sa.String(64), nullable=True),
        sa.Column("interactor_sha", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "judge_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "problem_id",
            sa.Integer(),
            sa.ForeignKey("judge_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("input_sha", sa.String(64), nullable=False),
        sa.Column("answer_sha", sa.String(64), nullable=True),
        sa.Column("group_name", sa.String(32), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.UniqueConstraint("problem_id", "index"),
    )
    op.create_table(
        "judge_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "problem_id",
            sa.Integer(),
            sa.ForeignKey("judge_problems.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("source_sha", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_time_ms", sa.Integer(), nullable=True),
        sa.Column("max_memory_kb", sa.Integer(), nullable=True),
        sa.Column("first_failed_test", sa.Integer(), nullable=True),
        sa.Column("compile_log_sha", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("judged_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_judge_submissions_status"), "judge_submissions", ["status"]
    )
    op.create_table(
        "judge_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("judge_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_index", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("memory_kb", sa.Integer(), nullable=False),
        sa.Column("points", sa.Float(), nullable=True),
        sa.Column("checker_comment", sa.Text(), nullable=True),
        sa.UniqueConstraint("submission_id", "test_index"),
    )


def downgrade() -> None:
    op.drop_table("judge_runs")
    op.drop_index(op.f("ix_judge_submissions_status"), table_name="judge_submissions")
    op.drop_table("judge_submissions")
    op.drop_table("judge_tests")
    op.drop_table("judge_problems")
