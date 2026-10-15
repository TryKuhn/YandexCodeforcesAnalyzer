import json

import httpx

from authoring.main import app
from tests.conftest import token
from tests.test_groups import PLAN


async def open_session(api, polygon_id):
    response = await api.get(f"/api/ai/problems/{polygon_id}/session")
    assert response.status_code == 200, response.text
    return response.json()


async def test_requires_valid_token(db_factory):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ai") as client:
        assert (await client.get("/api/ai/problems/1/session")).status_code in (401, 403)
        bad = await client.get("/api/ai/problems/1/session", headers={"Authorization": "Bearer junk"})
        assert bad.status_code == 401
        expired = await client.get("/api/ai/problems/1/session",
                                   headers={"Authorization": f"Bearer {token(minutes=-5)}"})
        assert expired.status_code == 401


async def test_models(api):
    data = (await api.get("/api/ai/models")).json()
    assert data["default"] == "anthropic/claude-opus-5.5"
    assert data["router"][0] == "anthropic/claude-haiku-5.5"
    assert [m["id"] for m in data["models"]] == [
        "anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5", "openai/gpt-6.1-sol"]


async def test_open_session_sync_and_notifications(api, backend, problem):
    session = await open_session(api, problem.id)
    assert session["polygon_id"] == problem.id and session["model"] == "anthropic/claude-opus-5.5"
    assert session["messages"] == [] and session["active_run"] is None
    again = await open_session(api, problem.id)
    assert again["session_id"] == session["session_id"]

    sid = session["session_id"]
    first = (await api.post(f"/api/ai/sessions/{sid}/sync")).json()
    assert first["event"] is None and first["last_synced_at"]
    problem.info["memoryLimit"] = 512
    second = (await api.post(f"/api/ai/sessions/{sid}/sync")).json()
    assert second["event"]["title"] == "ML: 256 МБ → 512 МБ"

    state = (await api.get(f"/api/ai/sessions/{sid}/state", params={"after_event": 0})).json()
    assert [e["title"] for e in state["events"]] == ["ML: 256 МБ → 512 МБ"]
    reopened = await open_session(api, problem.id)
    assert len(reopened["unseen_events"]) == 1
    await api.post(f"/api/ai/sessions/{sid}/events/seen", json={"up_to": reopened["last_event_id"]})
    assert (await open_session(api, problem.id))["unseen_events"] == []


async def test_sync_errors_are_reported(api, backend, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    backend.fail_paths[f"/polygon/problems/{problem.id}/info"] = (401, "Polygon API is not configured")
    response = await api.post(f"/api/ai/sessions/{sid}/sync")
    assert response.status_code == 502 and "not configured" in response.json()["detail"]


async def test_message_creates_run_and_state_shows_it(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    response = await api.post(f"/api/ai/sessions/{sid}/messages",
                              json={"text": "Почему TL?", "context": {"scope": "file", "file": "gen.cpp"}})
    assert response.status_code == 200
    data = response.json()
    assert data["run"]["kind"] == "chat" and data["run"]["status"] == "queued"
    assert data["message"]["meta"]["context"] == {"scope": "file", "file": "gen.cpp"}

    state = (await api.get(f"/api/ai/sessions/{sid}/state")).json()
    assert [m["content"] for m in state["messages"]] == ["Почему TL?"]
    assert state["active_run"]["id"] == data["run"]["id"]

    # syncing is postponed while a run is active
    assert (await api.post(f"/api/ai/sessions/{sid}/sync")).json()["skipped"] is True

    cancelled = (await api.post(f"/api/ai/runs/{data['run']['id']}/cancel")).json()
    assert cancelled["status"] == "cancelled"
    assert (await api.get(f"/api/ai/sessions/{sid}/state")).json()["active_run"] is None


async def test_other_users_cannot_touch_session(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    other = {"Authorization": f"Bearer {token(99)}"}
    assert (await api.get(f"/api/ai/sessions/{sid}/state", headers=other)).status_code == 404
    assert (await api.post(f"/api/ai/sessions/{sid}/messages", json={"text": "x"}, headers=other)).status_code == 404


async def test_patch_session(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    data = (await api.patch(f"/api/ai/sessions/{sid}", json={
        "model": "anthropic/claude-sonnet-4.6", "problem_type": "output_only", "auto_build": False})).json()
    assert data["model"] == "anthropic/claude-sonnet-5.5"
    assert data["problem_type"] == "output_only" and data["auto_build"] is False
    assert (await api.patch(f"/api/ai/sessions/{sid}", json={"problem_type": "weird"})).status_code == 422


async def test_plan_preview_get_and_groups_run(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    assert (await api.get(f"/api/ai/sessions/{sid}/plan")).json() == {"plan": None, "source": "empty"}

    preview = (await api.post(f"/api/ai/sessions/{sid}/plan/preview", json={"plan": PLAN})).json()
    assert preview["tests"] == 6 and preview["total_points"] == 100
    assert "gen_big 200000 random ${i + 4} > $" in preview["script"]

    bad = await api.post(f"/api/ai/sessions/{sid}/plan/preview", json={"plan": {"groups": []}})
    assert bad.status_code == 422 and "План групп" in bad.json()["detail"]

    run = (await api.post(f"/api/ai/sessions/{sid}/groups", json={"plan": PLAN})).json()["run"]
    assert run["kind"] == "groups"
    assert (await api.post(f"/api/ai/sessions/{sid}/groups", json={})).status_code == 422
    assert (await api.post(f"/api/ai/sessions/{sid}/scoring")).status_code == 409


async def test_build_is_deduplicated(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    first = (await api.post(f"/api/ai/sessions/{sid}/build")).json()
    second = (await api.post(f"/api/ai/sessions/{sid}/build")).json()
    assert first["already"] is False and second["already"] is True
    assert first["run"]["id"] == second["run"]["id"]
    assert (await api.get(f"/api/ai/sessions/{sid}/builds")).json() == []


async def test_create_problem_with_idea_queues_generation(api, backend):
    response = await api.post("/api/ai/problems", json={
        "name": "sum-two", "problem_type": "interactive", "idea": "сумма", "plan": PLAN})
    assert response.status_code == 200, response.text
    data = response.json()
    created = backend.problems[data["polygon_id"]]
    assert created.name == "sum-two" and created.info["interactive"] is True
    assert data["session"]["problem_type"] == "interactive"
    assert data["run"]["kind"] == "generate"

    plain = (await api.post("/api/ai/problems", json={"name": "clean"})).json()
    assert plain["run"] is None

    bad = await api.post("/api/ai/problems", json={"name": "x", "plan": {"groups": []}})
    assert bad.status_code == 422


async def test_solution_draft_and_skip(api, llm, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    llm.on("Напиши решение задачи с заданным тегом",
           lambda model, msgs: "SKIP: нельзя гарантировать ML" if "Тег: ML" in msgs[-1].parts[0].text
           else '<file role="solution" name="s.cpp">int main(){}</file>')
    ok = (await api.post(f"/api/ai/sessions/{sid}/solution-draft", json={"tag": "wa", "name": "wa.cpp"})).json()
    assert ok == {"skipped": False, "code": "int main(){}\n", "name": "wa.cpp", "tag": "WA"}
    skipped = (await api.post(f"/api/ai/sessions/{sid}/solution-draft", json={"tag": "ML"})).json()
    assert skipped == {"skipped": True, "reason": "нельзя гарантировать ML"}


async def test_checker_validator_assist(api, llm):
    llm.on("Выбери чекер", '<file role="checker" name="check.cpp">checker</file><reply>несколько ответов</reply>')
    llm.on("Напиши валидатор", '<file role="validator" name="v.cpp">validator</file>')
    data = (await api.post("/api/ai/assist/checker-validator", json={
        "statement": {"name": "A", "legend": "L", "input": "I", "output": "O", "time_limit": 1000}})).json()
    assert data == {"checker": {"type": "custom", "code": "checker\n"}, "validator": {"code": "validator\n"},
                    "comment": "несколько ответов"}
    assert "## Легенда\nL" in llm.calls[0].user


async def test_generate_endpoint_validates_plan(api, problem):
    sid = (await open_session(api, problem.id))["session_id"]
    bad = await api.post(f"/api/ai/sessions/{sid}/generate", json={"idea": "x", "plan": {"groups": [{}]}})
    assert bad.status_code == 422
    ok = (await api.post(f"/api/ai/sessions/{sid}/generate", json={"idea": "x", "groups": True})).json()
    assert ok["run"]["kind"] == "generate"
    session = await open_session(api, problem.id)
    assert session["messages"][-1]["meta"] == {"intent": "generate"}
    assert json.dumps(session["active_run"])  # serializable


async def test_cancel_running_run_sets_flag(api, problem, db_factory):
    from authoring.models import Run
    sid = (await open_session(api, problem.id))["session_id"]
    run = (await api.post(f"/api/ai/sessions/{sid}/messages", json={"text": "x"})).json()["run"]
    async with db_factory() as s:
        row = await s.get(Run, run["id"])
        row.status = "running"
        await s.commit()
    data = (await api.post(f"/api/ai/runs/{run['id']}/cancel")).json()
    assert data["status"] == "running"
    async with db_factory() as s:
        assert (await s.get(Run, run["id"])).cancel_requested is True
