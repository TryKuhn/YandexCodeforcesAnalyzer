"""Per-user integrations whose secrets are stored encrypted (see ``api.crypt.secrets``).

* :class:`EjudgeAccount` -- the user's own ejudge host for the Polygon -> ejudge export;
* :class:`LLMApiKey` -- the user's own LLM API key (OpenRouter / Anthropic / OpenAI) that the
  AI authoring service uses instead of the server's key;
* :class:`NlognAccount` -- the user's contest.nlogn.info admin token (publishing problems there);
* :class:`ApiToken` -- personal access tokens for the public API (``/api/public/v1``), e.g. for
  the NlogN admin pulling problems from here;
* :class:`NlognPublication` -- where a Polygon problem was published (ejudge contest/problem,
  NlogN problem), for prefilling the next publication.
"""
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, utcnow


class EjudgeAccount(Base):
    """SSH (key or password) + optional serve-control login of the user's ejudge."""
    __tablename__ = "user_ejudge_accounts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    ssh_host: Mapped[str] = mapped_column(String(255))
    ssh_port: Mapped[int] = mapped_column(default=22)
    ssh_user: Mapped[str] = mapped_column(String(64), default="ejudge")
    # "key" -> ssh_secret_enc is the private key text; "password" -> the SSH password
    auth_method: Mapped[str] = mapped_column(String(16))
    ssh_secret_enc: Mapped[str] = mapped_column(Text)
    ssh_key_passphrase_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # the server's host key: "SHA256:..." fingerprint or known_hosts line(s); public data
    host_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    insecure_host_key: Mapped[bool] = mapped_column(Boolean, default=False)

    judges_dir: Mapped[str] = mapped_column(String(255), default="/home/judges")
    web_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    web_login: Mapped[str | None] = mapped_column(String(100), nullable=True)
    web_password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # comma separated contest ids; empty = any contest
    allowed_contests: Mapped[str] = mapped_column(String(500), default="")

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class LLMApiKey(Base):
    """One API key per (user, provider)."""
    __tablename__ = "user_llm_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_llm_keys_user_provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(16))  # openrouter | anthropic | openai
    key_enc: Mapped[str] = mapped_column(Text)
    key_hint: Mapped[str] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class NlognAccount(Base):
    """An NlogN (contest.nlogn.info) admin token; the password itself is never stored."""
    __tablename__ = "user_nlogn_accounts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(255))
    token_enc: Mapped[str] = mapped_column(Text)
    nlogn_user_id: Mapped[int | None] = mapped_column(nullable=True)
    username: Mapped[str] = mapped_column(String(255), default="")
    full_name: Mapped[str] = mapped_column(String(255), default="")

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ApiToken(Base):
    """A personal access token: only its sha256 is stored, the token is shown once."""
    __tablename__ = "user_api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_hint: Mapped[str] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)


class NlognPublication(Base):
    """A Polygon problem published into an ejudge contest (and maybe into NlogN)."""
    __tablename__ = "nlogn_publications"
    __table_args__ = (
        UniqueConstraint("user_id", "polygon_id", "ejudge_contest_id", name="uq_nlogn_publications_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    polygon_id: Mapped[int] = mapped_column(index=True)
    package_id: Mapped[int | None] = mapped_column(nullable=True)
    revision: Mapped[int | None] = mapped_column(nullable=True)
    ejudge_contest_id: Mapped[int]
    ejudge_problem_id: Mapped[int]
    short_name: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="")
    nlogn_problem_id: Mapped[int | None] = mapped_column(nullable=True)
    nlogn_contest_id: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class EjudgeAutoContest(Base):
    """An ejudge contest this app created itself to hold published problems (blocks of N problems).

    ``host_key`` tells ejudge servers apart: the same contest number on two hosts is two contests.
    """
    __tablename__ = "ejudge_auto_contests"
    __table_args__ = (UniqueConstraint("host_key", "contest_id", name="uq_ejudge_auto_contests_host_contest"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_key: Mapped[str] = mapped_column(String(512), index=True)
    contest_id: Mapped[int]
    template_id: Mapped[int]
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

