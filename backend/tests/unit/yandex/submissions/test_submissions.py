"""Unit tests for api/user/yandex/submissions/submissions.py — handler wiring."""
import pytest
from fastapi import HTTPException

import api.user.yandex.submissions.submissions as submissions_mod
from api.pydantic_schemas import YandexSubmissions
from api.user.yandex.submissions.submissions import yandex_submissions
from models import Contest


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json


def _client_factory(*, list_response, source_text="src"):
    calls = {"gets": []}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, headers=None):
            calls["gets"].append(url)
            if url.endswith("/source"):
                return _FakeResponse(200, text=source_text)
            return list_response

    return _FakeClient, calls


def _payload(**over):
    base = dict(contest_id=100, from_pos=1, count=10)
    base.update(over)
    return YandexSubmissions(**base)


def _client_patch(monkeypatch, fake_cls):
    # AsyncClient is called with timeout=30.0 in the module.
    monkeypatch.setattr(
        submissions_mod.httpx, "AsyncClient", lambda *a, **k: fake_cls()
    )


@pytest.mark.asyncio
async def test_submissions_user_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        await yandex_submissions(_payload(), user_id=999999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_submissions_unconfigured_raises_401(db, user):
    with pytest.raises(HTTPException) as exc:
        await yandex_submissions(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected", [
    (400, 400), (403, 403), (404, 404), (500, 400),
])
async def test_submissions_list_error_codes(db, user, monkeypatch, code, expected):
    user.yandex_access_token = "TOK"
    await db.commit()
    fake_cls, _ = _client_factory(list_response=_FakeResponse(code, {}))
    _client_patch(monkeypatch, fake_cls)

    with pytest.raises(HTTPException) as exc:
        await yandex_submissions(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == expected


@pytest.mark.asyncio
async def test_submissions_401_unlinks_token(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    await db.commit()
    fake_cls, _ = _client_factory(list_response=_FakeResponse(401, {}))
    _client_patch(monkeypatch, fake_cls)

    with pytest.raises(HTTPException) as exc:
        await yandex_submissions(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    await db.refresh(user)
    assert user.yandex_access_token is None


@pytest.mark.asyncio
async def test_submissions_contest_not_in_db_raises_404(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    await db.commit()
    fake_cls, _ = _client_factory(
        list_response=_FakeResponse(200, {"submissions": [{"id": 1}]})
    )
    _client_patch(monkeypatch, fake_cls)

    with pytest.raises(HTTPException) as exc:
        await yandex_submissions(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 404
    assert "not found in database" in exc.value.detail


@pytest.mark.asyncio
async def test_submissions_happy_path(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    contest = Contest(
        id=1, user_id=user.id, platform="yandex", external_id=100,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.commit()

    fake_cls, calls = _client_factory(
        list_response=_FakeResponse(200, {"submissions": [{"id": 11}, {"id": 22}]}),
        source_text="THE-SOURCE",
    )
    _client_patch(monkeypatch, fake_cls)

    captured = {}

    async def fake_format(submissions, user_id, contest_id, db_):
        captured["format_args"] = (list(submissions), user_id, contest_id)
        return ["formatted"]

    monkeypatch.setattr(submissions_mod, "format_yandex_submissions", fake_format)

    async def fake_merge(subs, db_):
        captured["merge_subs"] = subs
        return {"merged": len(subs)}

    monkeypatch.setattr(submissions_mod, "merge_submissions", fake_merge)

    result = await yandex_submissions(_payload(), user_id=user.id, db=db)

    assert result == {"merged": 1}
    # contest_id passed to format is DB primary key (1), not external_id (100)
    subs_passed, uid, cid = captured["format_args"]
    assert uid == user.id
    assert cid == 1
    # each submission got its source fetched and attached
    assert all(s["source"] == "THE-SOURCE" for s in subs_passed)
    assert {s["id"] for s in subs_passed} == {11, 22}
    assert captured["merge_subs"] == ["formatted"]
