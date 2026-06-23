"""Unit tests for api.user.polygon.create_signature.create_signature.

The signature is `<rand6><sha512_hex>` where the hashed string is
`<rand6>/<method>?<sorted&params>#<secret>`. ``rand6`` comes from
``random.randrange`` (imported into the module as ``randrange``), so we
monkeypatch that to make the signature fully deterministic.
"""
import sys
from hashlib import sha512

from api.user.polygon.create_signature import create_signature

# The module file is named create_signature.py *and* defines a function of the
# same name, so plain ``import ... as cs`` would bind the function. Fetch the
# real module object from sys.modules to monkeypatch its ``randrange``.
cs = sys.modules["api.user.polygon.create_signature"]


def _patch_rand(monkeypatch, value: int):
    """Force ``randrange`` (used as ``f"{randrange(1000000):06d}"``) to return value."""
    monkeypatch.setattr(cs, "randrange", lambda *a, **k: value)


def test_signature_structure_is_rand6_plus_sha512_hex(monkeypatch):
    _patch_rand(monkeypatch, 42)
    sig = create_signature("problem.info", {"problemId": "5"}, "secret")

    # First 6 chars are the zero-padded random string.
    assert sig[:6] == "000042"
    # Remaining 128 chars are a SHA-512 hex digest.
    digest = sig[6:]
    assert len(digest) == 128
    assert all(c in "0123456789abcdef" for c in digest)


def test_signature_matches_manual_hash(monkeypatch):
    _patch_rand(monkeypatch, 123456)
    params = {"problemId": "5", "apiKey": "key", "time": "1000"}
    sig = create_signature("problem.info", params, "topsecret")

    sorted_params = sorted(params.items())
    expected_string = (
        "123456/problem.info?"
        + "&".join(f"{k}={v}" for k, v in sorted_params)
        + "#topsecret"
    )
    expected = "123456" + sha512(expected_string.encode()).hexdigest()
    assert sig == expected


def test_params_are_sorted_in_signature(monkeypatch):
    """Different insertion order yields the same signature (params are sorted)."""
    _patch_rand(monkeypatch, 7)
    a = create_signature("m", {"b": "2", "a": "1", "c": "3"}, "s")
    b = create_signature("m", {"c": "3", "a": "1", "b": "2"}, "s")
    assert a == b


def test_sorting_uses_key_value_pairs(monkeypatch):
    """Sorting is by (key, value) tuples — verify against the documented order."""
    _patch_rand(monkeypatch, 0)
    params = {"zeta": "1", "alpha": "9", "alpha2": "0"}
    sig = create_signature("method", params, "sec")

    sorted_kv = sorted(params.items())
    assert [k for k, _ in sorted_kv] == ["alpha", "alpha2", "zeta"]
    manual = (
        "000000/method?"
        + "&".join(f"{k}={v}" for k, v in sorted_kv)
        + "#sec"
    )
    assert sig == "000000" + sha512(manual.encode()).hexdigest()


def test_random_string_is_zero_padded_to_six(monkeypatch):
    _patch_rand(monkeypatch, 5)
    sig = create_signature("m", {}, "s")
    assert sig.startswith("000005")
    # Empty params -> "000005/m?#s"
    expected = "000005" + sha512("000005/m?#s".encode()).hexdigest()
    assert sig == expected


def test_secret_changes_signature(monkeypatch):
    _patch_rand(monkeypatch, 1)
    s1 = create_signature("m", {"a": "1"}, "secret1")
    s2 = create_signature("m", {"a": "1"}, "secret2")
    assert s1 != s2
    # Same rand prefix though.
    assert s1[:6] == s2[:6] == "000001"


def test_method_name_changes_signature(monkeypatch):
    _patch_rand(monkeypatch, 1)
    s1 = create_signature("problem.info", {"a": "1"}, "s")
    s2 = create_signature("problem.tests", {"a": "1"}, "s")
    assert s1 != s2
