"""user integrations: ejudge account and own LLM API keys

Revision ID: f6a7b8c9d0e1
Revises: d2e3f4a5b6c7
Create Date: 2026-10-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_ejudge_accounts",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ssh_host", sa.String(255), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("ssh_user", sa.String(64), nullable=False, server_default="ejudge"),
        sa.Column("auth_method", sa.String(16), nullable=False),
        sa.Column("ssh_secret_enc", sa.Text(), nullable=False),
        sa.Column("ssh_key_passphrase_enc", sa.Text(), nullable=True),
        sa.Column("host_key", sa.Text(), nullable=True),
        sa.Column("insecure_host_key", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("judges_dir", sa.String(255), nullable=False, server_default="/home/judges"),
        sa.Column("web_url", sa.String(255), nullable=True),
        sa.Column("web_login", sa.String(100), nullable=True),
        sa.Column("web_password_enc", sa.Text(), nullable=True),
        sa.Column("allowed_contests", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "user_llm_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("key_enc", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_llm_keys_user_provider"),
    )
    op.create_index("ix_user_llm_keys_user_id", "user_llm_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_llm_keys_user_id", table_name="user_llm_keys")
    op.drop_table("user_llm_keys")
    op.drop_table("user_ejudge_accounts")
