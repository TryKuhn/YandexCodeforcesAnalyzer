"""Unit tests for the Polygon API core (api.user.polygon.client)."""
import asyncio
import json
from enum import Enum

import aiohttp
import pytest
from fastapi import HTTPException

import api.user.polygon.client as client_mod
from api.user.polygon.client import (PolygonAPIError, PolygonParamError, call,
                                     choice, decode_text, encode_param,
                                     get_user, one_of, parse_response, request,
                                     signed_form, split_params)


# --------------------------------------------------------------------------
# Parameter encoding
# --------------------------------------------------------------------------
class _Color(Enum):
    RED = "red"


@pytest.mark.parametrize("value,expected", [
    (None, None),
    (True, "true"),
    (False, "false"),
    (5, "5"),
    (2.5, "2.5"),
    ("x", "x"),
    ("", ""),
    (_Color.RED, "red"),
    (["a", "b"], "a,b"),
    ((1, 2, 3), "1,2,3"),
    ([], ""),
    ([True, None, "x"], "true,x"),
    (b"raw", b"raw"),
])
def test_encode_param(value, expected):
    assert encode_param(value) == expected


def test_split_params_drops_none_and_signs_utf8_bytes():
    text, binary = split_params({
        "problemId": 5, "flag": True, "skip": None,
        "testInput": "5 6".encode(), "file": b"\x89PNG\xff\x00",
    })
    # Polygon signs content params, so UTF-8 bytes are text; only real binary is not.
    assert text == {"problemId": "5", "flag": "true", "testInput": "5 6"}
    assert binary == {"file": b"\x89PNG\xff\x00"}


def test_signed_form_adds_key_time_and_signature(monkeypatch):
    seen = {}

    def fake_sig(method, params, secret):
        seen.update(method=method, params=dict(params), secret=secret)
        return "SIG"

    monkeypatch.setattr(client_mod, "create_signature", fake_sig)
    monkeypatch.setattr(client_mod.time, "time", lambda: 1700000000.9)
    form = signed_form("problem.info", {"problemId": "5"}, "K", "S")
    assert form == {"apiKey": "K", "time": "1700000000", "problemId": "5", "apiSig": "SIG"}
    assert seen == {"method": "problem.info", "secret": "S",
                    "params": {"apiKey": "K", "time": "1700000000", "problemId": "5"}}


def test_decode_text_fallbacks():
    assert decode_text("привет".encode()) == "привет"
    assert decode_text("тест".encode("cp1251")) == "тест"
    assert decode_text(b"\x98") == b"\x98".decode("latin-1")


@pytest.mark.parametrize("value,allowed,expected", [
    ("complete-group", ("COMPLETE_GROUP", "EACH_TEST"), "COMPLETE_GROUP"),
    ("icpc", ("NONE", "ICPC"), "ICPC"),
    ("SOURCE", ("resource", "source"), "source"),
    (None, ("A",), None),
])
def test_choice_normalizes(value, allowed, expected):
    assert choice(value, allowed, "p") == expected


def test_choice_rejects_unknown():
    with pytest.raises(PolygonParamError, match="p: недопустимое значение 'x'"):
        choice("x", ("A", "B"), "p")


def test_one_of():
    one_of("m", a=1, b=None)
    with pytest.raises(PolygonParamError):
        one_of("m", a=None, b=None)
    with pytest.raises(PolygonParamError):
        one_of("m", a=1, b=2)


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------
def _ok(result):
    return json.dumps({"status": "OK", "result": result}).encode()


def test_parse_json_ok_returns_result():
    assert parse_response("m", 200, _ok({"id": 1}), "json") == {"id": 1}


def test_parse_json_ok_without_result_is_none():
    assert parse_response("m", 200, b'{"status": "OK"}', "json") is None


def test_parse_failed_raises_with_comment_and_result():
    body = json.dumps({
        "status": "FAILED", "comment": "cannot delete",
        "result": {"failures": [{"index": 3, "reason": "FREEMARKER_SCRIPT_TEST"}]},
    }).encode()
    with pytest.raises(PolygonAPIError) as exc:
        parse_response("problem.deleteTest", 400, body, "json")
    assert str(exc.value) == "cannot delete"
    assert exc.value.http_status == 400
    assert exc.value.method == "problem.deleteTest"
    assert exc.value.result["failures"][0]["index"] == 3


def test_parse_json_non_envelope_200_raises():
    with pytest.raises(PolygonAPIError, match="неожиданный ответ"):
        parse_response("m", 200, b"plain", "json")


def test_parse_html_gateway_error_is_short():
    with pytest.raises(PolygonAPIError) as exc:
        parse_response("m", 502, b"<html><body>Bad gateway</body></html>", "json")
    assert exc.value.http_status == 502
    assert "временно недоступен" in str(exc.value)
    assert "<html" in exc.value.raw_response


@pytest.mark.parametrize("body", [b"190", b"true", b"[1, 2]", b'{"a": 1}', b"5 6\n"])
def test_parse_text_returns_body_verbatim(body):
    # testInput "190" must stay the string "190", not become an int / envelope.
    assert parse_response("problem.testInput", 200, body, "text") == body.decode()


def test_parse_text_decodes_cp1251():
    assert parse_response("problem.viewFile", 200, "тест".encode("cp1251"), "text") == "тест"


def test_parse_bytes_returns_raw():
    blob = b"PK\x03\x04\xff"
    assert parse_response("problem.package", 200, blob, "bytes") == blob


def test_parse_raw_kinds_still_detect_failed_envelope():
    body = b'{"status": "FAILED", "comment": "no such file"}'
    for kind in ("text", "bytes"):
        with pytest.raises(PolygonAPIError, match="no such file"):
            parse_response("problem.viewFile", 400, body, kind)


# --------------------------------------------------------------------------
# request(): transport, signing, retries
# --------------------------------------------------------------------------
class _Resp:
    def __init__(self, status, body):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode()

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    """Scripted aiohttp session: each item is a _Resp or an exception to raise."""

    def __init__(self, *script):
        self.script = list(script)
        self.posts = []

    def post(self, url, data=None):
        self.posts.append((url, dict(data)))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            class _Raise:
                async def __aenter__(_self):
                    raise item

                async def __aexit__(_self, *e):
                    return False
            return _Raise()
        return item


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(client_mod, "_sleep", fake_sleep)
    return slept


@pytest.fixture
def counting_sig(monkeypatch):
    calls = []

    def fake_sig(method, params, secret):
        calls.append(dict(params))
        return f"SIG{len(calls)}"

    monkeypatch.setattr(client_mod, "create_signature", fake_sig)
    return calls


async def test_request_posts_signed_form_to_method_url(counting_sig, no_sleep):
    session = _Session(_Resp(200, _ok([1])))
    out = await request("problem.tests", {"problemId": 5, "noInputs": True},
                        api_key="K", api_secret="S", session=session)
    assert out == [1]
    url, form = session.posts[0]
    assert url.endswith("/problem.tests")
    assert form["apiKey"] == "K" and form["apiSig"] == "SIG1"
    assert form["problemId"] == "5" and form["noInputs"] == "true"


async def test_request_binary_param_is_sent_and_signed(counting_sig, no_sleep):
    session = _Session(_Resp(200, _ok(None)))
    await request("problem.saveStatementResource",
                  {"problemId": 5, "name": "a.png", "file": b"\x89PNG\xff"},
                  api_key="K", api_secret="S", session=session)
    # Polygon signs every parameter, binary file content included (byte-for-byte).
    assert counting_sig[0]["file"] == b"\x89PNG\xff"
    assert session.posts[0][1]["file"] == b"\x89PNG\xff"


@pytest.mark.parametrize("method", sorted(client_mod.NOT_REPEATABLE_METHODS))
async def test_request_side_effect_methods_not_repeated_after_5xx(counting_sig, no_sleep,
                                                                  method):
    session = _Session(_Resp(502, "<html>bad gateway</html>"), _Resp(200, _ok(1)))
    with pytest.raises(PolygonAPIError) as exc:
        await request(method, {}, api_key="K", api_secret="S", session=session)
    assert exc.value.http_status == 502
    assert len(session.posts) == 1


async def test_request_side_effect_methods_not_repeated_after_timeout(counting_sig, no_sleep):
    session = _Session(asyncio.TimeoutError(), _Resp(200, _ok(1)))
    with pytest.raises(PolygonAPIError):
        await request("problem.buildPackage", {}, api_key="K", api_secret="S",
                      session=session)
    assert len(session.posts) == 1


async def test_request_side_effect_methods_retry_rate_limit(counting_sig, no_sleep):
    # Rejected before execution -> safe to repeat even for problem.create.
    failed = json.dumps({"status": "FAILED", "comment": "time is not within 5 minutes"})
    session = _Session(_Resp(400, failed), _Resp(200, _ok({"id": 9})))
    out = await request("problem.create", {"name": "x"}, api_key="K", api_secret="S",
                        session=session)
    assert out == {"id": 9}


async def test_request_retries_5xx_and_resigns(counting_sig, no_sleep):
    session = _Session(_Resp(503, "<html>down</html>"), _Resp(200, _ok(42)))
    assert await request("m", {}, api_key="K", api_secret="S", session=session) == 42
    assert len(session.posts) == 2
    # A fresh signature (and time) per attempt.
    assert [p[1]["apiSig"] for p in session.posts] == ["SIG1", "SIG2"]
    assert no_sleep == [client_mod.RETRY_BACKOFF_SECONDS]


@pytest.mark.parametrize("comment", [
    "Too many requests", "time is not within 5 minutes", "Please try again later",
])
async def test_request_retries_transient_comments(counting_sig, no_sleep, comment):
    failed = json.dumps({"status": "FAILED", "comment": comment})
    session = _Session(_Resp(400, failed), _Resp(200, _ok("done")))
    assert await request("m", {}, api_key="K", api_secret="S", session=session) == "done"


async def test_request_logical_error_is_not_retried(counting_sig, no_sleep):
    session = _Session(_Resp(400, '{"status": "FAILED", "comment": "testset: not found"}'))
    with pytest.raises(PolygonAPIError, match="testset: not found"):
        await request("m", {}, api_key="K", api_secret="S", session=session)
    assert len(session.posts) == 1 and no_sleep == []


async def test_request_network_errors_exhaust_to_502(counting_sig, no_sleep):
    errors = [aiohttp.ClientError("reset")] * (client_mod.MAX_ATTEMPTS - 1)
    session = _Session(*errors, asyncio.TimeoutError())
    with pytest.raises(PolygonAPIError) as exc:
        await request("m", {}, api_key="K", api_secret="S", session=session)
    assert exc.value.http_status == 502
    assert len(session.posts) == client_mod.MAX_ATTEMPTS
    assert len(no_sleep) == client_mod.MAX_ATTEMPTS - 1


async def test_request_kind_text(counting_sig, no_sleep):
    session = _Session(_Resp(200, "1 5\n"))
    out = await request("problem.testInput", {}, api_key="K", api_secret="S",
                        kind="text", session=session)
    assert out == "1 5\n"


async def test_request_opens_own_session_when_none(monkeypatch, counting_sig, no_sleep):
    session = _Session(_Resp(200, _ok("x")))

    class _Ctx:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return session

        async def __aexit__(self, *e):
            return False

    monkeypatch.setattr(client_mod.aiohttp, "ClientSession", _Ctx)
    assert await request("m", {}, api_key="K", api_secret="S") == "x"


# --------------------------------------------------------------------------
# get_user / call
# --------------------------------------------------------------------------
async def test_get_user_returns_user(db, user):
    assert (await get_user(user.id, db)).id == user.id


@pytest.mark.parametrize("field", ["polygon_api_key", "polygon_api_secret"])
async def test_get_user_without_credentials_is_401(db, user, field):
    setattr(user, field, None)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await get_user(user.id, db)
    assert exc.value.status_code == 401


async def test_get_user_missing_user_is_401(db):
    with pytest.raises(HTTPException) as exc:
        await get_user(999999, db)
    assert exc.value.status_code == 401


async def test_call_uses_user_credentials(polygon_api, db, user):
    polygon_api.respond("problem.info", {"timeLimit": 1000})
    assert await call("problem.info", user.id, db, problemId=5) == {"timeLimit": 1000}
    sent = polygon_api.last()
    assert (sent.api_key, sent.api_secret, sent.params) == ("key", "secret", {"problemId": "5"})


async def test_request_unexpected_200_body_is_not_retried(counting_sig, no_sleep):
    session = _Session(_Resp(200, "<html>login page</html>"))
    with pytest.raises(PolygonAPIError, match="неожиданный ответ"):
        await request("m", {}, api_key="K", api_secret="S", session=session)
    assert len(session.posts) == 1
