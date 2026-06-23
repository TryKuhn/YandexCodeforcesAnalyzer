"""Unit tests for api/user/yandex/standings/standings.py — handler wiring."""
import pytest
from fastapi import HTTPException

import api.user.yandex.standings.standings as standings_mod
from api.pydantic_schemas import YandexStandings
from api.user.yandex.standings.standings import yandex_standings


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


def _client_factory(get_responses):
    """get_responses: list consumed in order, one per .get() call."""
    calls = {"gets": [], "responses": list(get_responses)}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, headers=None):
            calls["gets"].append({"url": url, "params": params})
            return calls["responses"].pop(0)

    return _FakeClient, calls


def _payload(**over):
    base = dict(contest_id=100, as_manager=False, from_pos=1, count=10,
                show_unofficial=False)
    base.update(over)
    return YandexStandings(**base)


@pytest.mark.asyncio
async def test_standings_user_not_found_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        await yandex_standings(_payload(), user_id=999999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_standings_unconfigured_raises_401(db, user):
    # user fixture has no yandex token.
    with pytest.raises(HTTPException) as exc:
        await yandex_standings(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected", [
    (400, 400), (403, 403), (404, 404), (500, 400),
])
async def test_standings_contest_info_error_codes(db, user, monkeypatch, code, expected):
    user.yandex_access_token = "TOK"
    await db.commit()
    fake_cls, _ = _client_factory([_FakeResponse(code, {})])
    monkeypatch.setattr(standings_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_standings(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == expected


@pytest.mark.asyncio
async def test_standings_401_unlinks_token(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    await db.commit()
    fake_cls, _ = _client_factory([_FakeResponse(401, {})])
    monkeypatch.setattr(standings_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_standings(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    await db.refresh(user)
    assert user.yandex_access_token is None


@pytest.mark.asyncio
async def test_standings_standings_data_error_raises_400(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    await db.commit()
    # contest_info OK, standings_data fails
    fake_cls, _ = _client_factory([
        _FakeResponse(200, {"name": "C", "standingsPlugin": "acm"}),
        _FakeResponse(500, {}),
    ])
    monkeypatch.setattr(standings_mod.httpx, "AsyncClient", lambda: fake_cls())

    with pytest.raises(HTTPException) as exc:
        await yandex_standings(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_standings_happy_path_calls_format_and_merge(db, user, monkeypatch):
    user.yandex_access_token = "TOK"
    await db.commit()

    fake_cls, calls = _client_factory([
        _FakeResponse(200, {"name": "C", "standingsPlugin": "acm"}),
        _FakeResponse(200, {"titles": [], "rows": []}),
    ])
    monkeypatch.setattr(standings_mod.httpx, "AsyncClient", lambda: fake_cls())

    captured = {}

    def fake_format(contest_info, standings_data, user_id, unofficial):
        captured["format_args"] = (contest_info, standings_data, user_id, unofficial)
        return ("contest", ["task"], ["row"])

    monkeypatch.setattr(standings_mod, "format_yandex_standings", fake_format)

    async def fake_merge(contest, tasks, rows, user_id, db_):
        captured["merge_args"] = (contest, tasks, rows, user_id)
        return {"merged": True}

    monkeypatch.setattr(standings_mod, "merge_table", fake_merge)

    result = await yandex_standings(
        _payload(show_unofficial=True), user_id=user.id, db=db
    )

    assert result == {"merged": True}
    # contest_info injected with the requested contest_id
    contest_info = captured["format_args"][0]
    assert contest_info["id"] == 100
    assert captured["format_args"][2] == user.id
    assert captured["format_args"][3] is True  # unofficial flag
    assert captured["merge_args"] == ("contest", ["task"], ["row"], user.id)
    # standings request used pagination params + unofficial flags
    standings_get = calls["gets"][1]["params"]
    assert standings_get["showExternal"] == "true"
    assert standings_get["showVirtual"] == "true"
    assert standings_get["pageSize"] == 10
