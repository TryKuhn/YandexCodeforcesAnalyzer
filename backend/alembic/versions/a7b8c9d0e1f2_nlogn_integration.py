"""NlogN integration: NlogN account, personal API tokens, publications

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_nlogn_accounts",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("nlogn_user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(255), nullable=False, server_default=""),
        sa.Column("full_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user_api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_hint", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_api_tokens_user_id", "user_api_tokens", ["user_id"])
    op.create_table(
        "nlogn_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("polygon_id", sa.Integer(), nullable=False),
        sa.Column("package_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("ejudge_contest_id", sa.Integer(), nullable=False),
        sa.Column("ejudge_problem_id", sa.Integer(), nullable=False),
        sa.Column("short_name", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("nlogn_problem_id", sa.Integer(), nullable=True),
        sa.Column("nlogn_contest_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "polygon_id", "ejudge_contest_id", name="uq_nlogn_publications_target"),
    )
    op.create_index("ix_nlogn_publications_user_id", "nlogn_publications", ["user_id"])
    op.create_index("ix_nlogn_publications_polygon_id", "nlogn_publications", ["polygon_id"])


def downgrade() -> None:
    op.drop_index("ix_nlogn_publications_polygon_id", table_name="nlogn_publications")
    op.drop_index("ix_nlogn_publications_user_id", table_name="nlogn_publications")
    op.drop_table("nlogn_publications")
    op.drop_index("ix_user_api_tokens_user_id", table_name="user_api_tokens")
    op.drop_table("user_api_tokens")
    op.drop_table("user_nlogn_accounts")
