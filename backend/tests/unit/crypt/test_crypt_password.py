"""Unit tests for api/crypt/crypt_password.py — password hashing & token hashing."""
import hashlib

from api.crypt.crypt_password import hash_password, hash_token, verify_password


def test_hash_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert hashed != "s3cret!"
    assert verify_password("s3cret!", hashed) is True


def test_verify_password_rejects_wrong():
    hashed = hash_password("correct-horse")
    assert verify_password("wrong", hashed) is False


def test_hash_password_is_salted_unique():
    h1 = hash_password("same")
    h2 = hash_password("same")
    # bcrypt salts each hash, so two hashes of the same input differ
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_hash_token_matches_sha256():
    token = "my-refresh-token"
    expected = hashlib.sha256(token.encode()).hexdigest()
    assert hash_token(token) == expected


def test_hash_token_deterministic():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
