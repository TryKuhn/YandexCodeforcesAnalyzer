"""Unit tests for the statement push (services.sync.statement_sync)."""
import pytest

from api.user.gpt.services.sync import statement_sync as st
from models.task.session import ProblemType


def _record(bucket, name):
    async def fake(*args, **kwargs):
        bucket.append((name, args, kwargs))
    return fake


def _patch(monkeypatch):
    calls = []
    for name in ("save_statement", "commit_changes"):
        monkeypatch.setattr(
            f"api.user.gpt.services.sync.statement_sync.{name}",
            _record(calls, name),
        )
    return calls


@pytest.mark.asyncio
async def test_sync_statement_forwards_fields_and_commits(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    statement = {
        "name": "Sum", "legend": "Add two numbers",
        "input": "two ints", "output": "their sum",
        "notes": "n", "tutorial": "t", "scoring": "100 pts",
    }
    pid = await st.sync_statement(db, task_session, statement)
    assert pid == 555

    save = [c for c in calls if c[0] == "save_statement"][0]
    kwargs = save[2]
    assert kwargs["name"] == "Sum"
    assert kwargs["legend"] == "Add two numbers"
    assert kwargs["input_legend"] == "two ints"
    assert kwargs["output_legend"] == "their sum"
    assert kwargs["notes"] == "n"
    assert kwargs["tutorial"] == "t"
    assert kwargs["scoring"] == "100 pts"
    assert kwargs["lang"] == "russian"
    # REGULAR -> interaction suppressed
    assert kwargs["interaction"] == ""
    assert [c[0] for c in calls].count("commit_changes") == 1


@pytest.mark.asyncio
async def test_sync_statement_interaction_only_for_interactive(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    task_session.problem_type = ProblemType.INTERACTIVE
    await db.commit()

    await st.sync_statement(
        db, task_session, {"interaction": "talk to the judge"}
    )
    save = [c for c in calls if c[0] == "save_statement"][0]
    assert save[2]["interaction"] == "talk to the judge"


@pytest.mark.asyncio
async def test_sync_statement_regular_drops_interaction(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    # REGULAR session, statement carries interaction -> must be dropped
    await st.sync_statement(
        db, task_session, {"interaction": "should be ignored"}
    )
    save = [c for c in calls if c[0] == "save_statement"][0]
    assert save[2]["interaction"] == ""


@pytest.mark.asyncio
async def test_sync_statement_custom_lang_and_no_commit(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    await st.sync_statement(
        db, task_session, {"name": "X"}, lang="english", polygon_commit=False
    )
    save = [c for c in calls if c[0] == "save_statement"][0]
    assert save[2]["lang"] == "english"
    assert "commit_changes" not in [c[0] for c in calls]
