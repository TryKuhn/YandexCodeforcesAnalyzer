"""Encryption at rest for user secrets (SSH keys/passwords, LLM API keys).

Fernet (AES-128-CBC + HMAC-SHA256) with a key derived from ``SECRET_KEY`` by
HKDF, so no extra setting is needed. Rotating ``SECRET_KEY`` makes the stored
secrets unreadable: :func:`decrypt` then raises :class:`SecretError` and the
user is asked to link the integration again.
"""
from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from settings import settings

_INFO = b"yca-user-secrets-v1"


class SecretError(Exception):
    """A stored secret cannot be decrypted (e.g. SECRET_KEY was changed)."""


@lru_cache(maxsize=4)
def _fernet(secret_key: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    """Opaque ASCII token for ``value``."""
    return _fernet(settings.SECRET_KEY).encrypt(value.encode()).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet(settings.SECRET_KEY).decrypt(token.encode("ascii")).decode()
    except (InvalidToken, ValueError) as e:
        raise SecretError("сохранённый секрет не расшифровывается (сменился SECRET_KEY?): привяжите заново") from e


def encrypt_optional(value: str | None) -> str | None:
    return encrypt(value) if value else None


def decrypt_optional(token: str | None) -> str:
    return decrypt(token) if token else ""


def hint(value: str) -> str:
    """A safe-to-show hint of a key: its prefix and last 4 characters."""
    value = value.strip()
    if len(value) <= 8:
        return "…" + value[-2:]
    prefix = value[: min(6, len(value) // 4)]
    return f"{prefix}…{value[-4:]}"
