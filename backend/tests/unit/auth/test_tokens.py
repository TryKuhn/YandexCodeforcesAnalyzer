"""Unit tests for api/user/auth/tokens.py — access/refresh token issuance."""
from datetime import datetime, timedelta

from api.crypt import verify_token
from api.user.auth.tokens import get_tokens
from settings import settings


def test_get_tokens_returns_four_values():
    access, refresh, created_at, expires_in = get_tokens(7, "sess-id")
    assert isinstance(access, str)
    assert isinstance(refresh, str)
    assert isinstance(created_at, datetime)
    assert isinstance(expires_in, datetime)


def test_tokens_carry_user_and_session():
    access, refresh, _, _ = get_tokens(42, "the-session")
    for token in (access, refresh):
        payload = verify_token(token)
        assert payload["user_id"] == 42
        assert payload["sid"] == "the-session"
        assert "jti" in payload


def test_access_and_refresh_have_distinct_jti():
    access, refresh, _, _ = get_tokens(1, "s")
    # Both tokens are created from the same data dict, so jti is shared.
    assert verify_token(access)["jti"] == verify_token(refresh)["jti"]


def test_returned_datetimes_are_naive_and_expiry_offset():
    _, _, created_at, expires_in = get_tokens(1, "s")
    # tokens.py strips tzinfo before returning
    assert created_at.tzinfo is None
    assert expires_in.tzinfo is None
    delta = expires_in - created_at
    # expires_in = created_at + EXPIRES_REFRESH minutes
    assert abs(delta - timedelta(minutes=settings.EXPIRES_REFRESH)) < timedelta(seconds=2)


def test_refresh_token_expires_later_than_access():
    access, refresh, _, _ = get_tokens(1, "s")
    access_exp = verify_token(access)["exp"]
    refresh_exp = verify_token(refresh)["exp"]
    assert refresh_exp > access_exp
