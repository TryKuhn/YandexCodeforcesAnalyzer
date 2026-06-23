"""Unit tests for api/crypt/jwt_token.py — token create/verify and get_current_user."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.crypt.jwt_token import (create_token, get_current_payload,
                                 get_current_user, verify_token)
from settings import settings


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_and_verify_token_roundtrip():
    now = datetime.now(timezone.utc)
    token = create_token({"user_id": 7, "sid": "abc"}, created_at=now, expires_delta=30)
    payload = verify_token(token)
    assert payload["user_id"] == 7
    assert payload["sid"] == "abc"
    assert "exp" in payload


def test_create_token_sets_correct_exp():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    token = create_token({"user_id": 1}, created_at=now, expires_delta=15)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    expected_exp = int((now + timedelta(minutes=15)).timestamp())
    assert payload["exp"] == expected_exp


def test_verify_token_expired_raises_401():
    now = datetime.now(timezone.utc) - timedelta(hours=2)
    token = create_token({"user_id": 1}, created_at=now, expires_delta=1)
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_verify_token_invalid_raises_401():
    with pytest.raises(HTTPException) as exc:
        verify_token("not-a-valid-jwt")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


def test_get_current_user_returns_user_id():
    now = datetime.now(timezone.utc)
    token = create_token({"user_id": 42}, created_at=now, expires_delta=30)
    assert get_current_user(_creds(token)) == 42


def test_get_current_user_missing_user_id_raises_401():
    now = datetime.now(timezone.utc)
    token = create_token({"sid": "no-user"}, created_at=now, expires_delta=30)
    with pytest.raises(HTTPException) as exc:
        get_current_user(_creds(token))
    assert exc.value.status_code == 401
    assert "User ID not found" in exc.value.detail


def test_get_current_user_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user(_creds("garbage"))
    assert exc.value.status_code == 401


def test_get_current_payload_returns_full_payload():
    now = datetime.now(timezone.utc)
    token = create_token({"user_id": 9, "sid": "s1"}, created_at=now, expires_delta=30)
    payload = get_current_payload(_creds(token))
    assert payload["user_id"] == 9
    assert payload["sid"] == "s1"
