"""Unit tests for api/user/codeforces/create_signature.py — CF apiSig builder."""
from hashlib import sha512

import pytest

from api.user.codeforces import create_signature as sig_mod
from api.user.codeforces.create_signature import create_signature


@pytest.mark.asyncio
async def test_signature_format_and_value(monkeypatch):
    # Pin the random prefix so the result is deterministic.
    monkeypatch.setattr(sig_mod, "randrange", lambda n: 123)

    params = {"b": "2", "a": "1"}
    result = await create_signature("contest.standings", params, "SECRET")

    rand = "000123"
    # Params must be sorted by key for the signature string.
    expected_str = f"{rand}/contest.standings?a=1&b=2#SECRET"
    expected_hash = sha512(expected_str.encode()).hexdigest()
    assert result == f"{rand}{expected_hash}"
    assert result.startswith(rand)
    assert len(result) == 6 + 128  # 6-digit prefix + sha512 hexdigest


@pytest.mark.asyncio
async def test_signature_sorts_params(monkeypatch):
    monkeypatch.setattr(sig_mod, "randrange", lambda n: 0)
    # Same params in different insertion order produce identical signature.
    s1 = await create_signature("m", {"x": "1", "y": "2"}, "s")
    s2 = await create_signature("m", {"y": "2", "x": "1"}, "s")
    assert s1 == s2


@pytest.mark.asyncio
async def test_signature_changes_with_secret(monkeypatch):
    monkeypatch.setattr(sig_mod, "randrange", lambda n: 5)
    s1 = await create_signature("m", {"a": "1"}, "secret1")
    s2 = await create_signature("m", {"a": "1"}, "secret2")
    assert s1 != s2
