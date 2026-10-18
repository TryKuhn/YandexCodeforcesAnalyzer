"""authoring: initial tables

Revision ID: a1a0000000001
Revises:
Create Date: 2026-10-09 18:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1a0000000001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authoring_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("polygon_id", sa.Integer(), nullable=False),
        sa.Column("problem_type", sa.String(16), nullable=False, server_default="regular"),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_opened_at", sa.DateTime(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "polygon_id", name="uq_authoring_session"),
    )
    op.create_index("ix_authoring_sessions_user_id", "authoring_sessions", ["user_id"])
    op.create_index("ix_authoring_sessions_polygon_id", "authoring_sessions", ["polygon_id"])

    op.create_table(
        "authoring_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("authoring_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_authoring_messages_session_id", "authoring_messages", ["session_id"])

    op.create_table(
        "authoring_snapshots",
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("authoring_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("taken_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "authoring_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("authoring_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("seen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_authoring_events_session_id", "authoring_events", ["session_id"])

    op.create_table(
        "authoring_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("authoring_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("parent_run_id", sa.String(36), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_authoring_runs_session_id", "authoring_runs", ["session_id"])
    op.create_index("ix_authoring_runs_status", "authoring_runs", ["status"])

    op.create_table(
        "authoring_builds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("authoring_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_authoring_builds_session_id", "authoring_builds", ["session_id"])
    op.create_index("ix_authoring_builds_run_id", "authoring_builds", ["run_id"])


def downgrade() -> None:
    op.drop_table("authoring_builds")
    op.drop_table("authoring_runs")
    op.drop_table("authoring_events")
    op.drop_table("authoring_snapshots")
    op.drop_table("authoring_messages")
    op.drop_table("authoring_sessions")
