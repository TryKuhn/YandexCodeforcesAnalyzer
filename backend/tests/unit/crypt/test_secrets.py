"""Encryption at rest of user secrets."""
import pytest

from api.crypt import secrets
from settings import settings


def test_roundtrip_and_opaque_token():
    token = secrets.encrypt("sk-ant-api03-secret")
    assert "secret" not in token
    assert secrets.decrypt(token) == "sk-ant-api03-secret"
    assert secrets.encrypt("same") != secrets.encrypt("same")  # random IV


def test_optional_helpers():
    assert secrets.encrypt_optional("") is None and secrets.encrypt_optional(None) is None
    assert secrets.decrypt_optional(None) == ""
    assert secrets.decrypt_optional(secrets.encrypt("x")) == "x"


def test_changed_secret_key_is_a_clear_error(monkeypatch):
    token = secrets.encrypt("value")
    monkeypatch.setattr(settings, "SECRET_KEY", settings.SECRET_KEY + "-rotated")
    with pytest.raises(secrets.SecretError, match="привяжите заново"):
        secrets.decrypt(token)
    with pytest.raises(secrets.SecretError):
        secrets.decrypt("not a token")


def test_hint_hides_the_key():
    assert secrets.hint("sk-or-v1-0123456789abcdef") == "sk-or-…cdef"
    assert "0123" not in secrets.hint("sk-or-v1-0123456789abcdef")
    assert secrets.hint("short") == "…rt"
