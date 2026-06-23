"""Unit tests for api/user/codeforces/submissions/submissions.py — handler wiring."""
import pytest
from fastapi import HTTPException

import api.user.codeforces.submissions.submissions as submissions_mod
from api.pydantic_schemas import Submissions
from api.user.codeforces.submissions.submissions import codeforces_submissions
from models import Contest


class _FakeClientSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _payload():
    return Submissions(
        contest_id=100,
        as_manager=False,
        from_pos=1,
        count=10,
        include_source=True,
    )


@pytest.mark.asyncio
async def test_submissions_unconfigured_cf_raises_401(db, user):
    with pytest.raises(HTTPException) as exc:
        await codeforces_submissions(_payload(), user_id=user.id, db=db)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


@pytest.mark.asyncio
async def test_submissions_happy_path(db, user, monkeypatch):
    user.codeforces_api_key = "K"
    user.codeforces_api_secret = "S"
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=100,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.commit()

    monkeypatch.setattr(submissions_mod, "ClientSession", lambda: _FakeClientSession())

    captured = {}

    async def fake_get_response(client, url, params):
        captured["params"] = params
        return [{"raw": "sub"}]

    monkeypatch.setattr(submissions_mod, "get_response", fake_get_response)

    async def fake_format(response, user_id, contest_id, db_):
        captured["format_args"] = (response, user_id, contest_id)
        return ["formatted_sub"]

    monkeypatch.setattr(submissions_mod, "format_codeforces_submissions", fake_format)

    async def fake_merge(subs, db_):
        captured["merge_subs"] = subs
        return {"merged": len(subs)}

    monkeypatch.setattr(submissions_mod, "merge_submissions", fake_merge)

    result = await codeforces_submissions(_payload(), user_id=user.id, db=db)

    assert result == {"merged": 1}
    assert captured["params"]["apiKey"] == "K"
    assert "apiSig" in captured["params"]
    # contest_id passed to format is the DB primary key (1), not external_id
    assert captured["format_args"] == ([{"raw": "sub"}], user.id, 1)
    assert captured["merge_subs"] == ["formatted_sub"]
