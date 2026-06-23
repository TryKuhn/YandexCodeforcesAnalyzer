"""Unit tests for api/user/codeforces/standings/standings.py — handler wiring."""
import pytest
from fastapi import HTTPException

import api.user.codeforces.standings.standings as standings_mod
from api.pydantic_schemas import Standings
from api.user.codeforces.standings.standings import codeforces_standings


class _FakeClientSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _payload():
    return Standings(
        contest_id=100,
        as_manager=False,
        from_pos=1,
        count=10,
        show_unofficial=False,
    )


@pytest.mark.asyncio
async def test_standings_unconfigured_cf_raises_401(db, user):
    # user fixture has no CF key set.
    with pytest.raises(HTTPException) as exc:
        await codeforces_standings(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


@pytest.mark.asyncio
async def test_standings_happy_path_calls_format_and_merge(db, user, monkeypatch):
    user.codeforces_api_key = "K"
    user.codeforces_api_secret = "S"
    await db.commit()

    monkeypatch.setattr(standings_mod, "ClientSession", lambda: _FakeClientSession())

    captured = {}

    async def fake_get_response(client, url, params):
        captured["params"] = params
        return {"raw": "standings"}

    monkeypatch.setattr(standings_mod, "get_response", fake_get_response)

    def fake_format(response, user_id, show_unofficial):
        captured["format_args"] = (response, user_id, show_unofficial)
        return ("contest", ["task"], ["row"])

    monkeypatch.setattr(standings_mod, "format_codeforces_standings", fake_format)

    async def fake_merge(contest, tasks, rows, user_id, db_):
        captured["merge_args"] = (contest, tasks, rows, user_id)
        return {"merged": True}

    monkeypatch.setattr(standings_mod, "merge_table", fake_merge)

    result = await codeforces_standings(_payload(), user_id=user.id, db=db)

    assert result == {"merged": True}
    # apiSig must be present and signature built; request used correct apiKey
    assert captured["params"]["apiKey"] == "K"
    assert "apiSig" in captured["params"]
    assert captured["format_args"] == ({"raw": "standings"}, user.id, False)
    assert captured["merge_args"] == ("contest", ["task"], ["row"], user.id)
