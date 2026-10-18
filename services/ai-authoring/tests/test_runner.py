import json
from datetime import timedelta

from sqlalchemy import select

from authoring.db import utcnow
from authoring.models import AuthoringSession, Event, Message, Run
from authoring.pipeline.runner import Worker, enqueue
from tests.conftest import USER_ID


def make_worker(db_factory, llm, client_factory) -> Worker:
    return Worker(db_factory, llm=llm, client_factory=client_factory)


async def runs(db_factory):
    async with db_factory() as db:
        return (await db.execute(select(Run).order_by(Run.created_at))).scalars().all()


async def test_chat_run_chains_a_build(db_factory, db, session_row, llm, client_factory, backend, problem):
    llm.on("маршрутизатор", json.dumps({"intent": "modify", "targets": ["validator"]}))
    llm.on("Ты вносишь изменения", '<file role="validator" name="v.cpp">int main(){}</file>')
    run = await enqueue(db, session_row, "chat", {"text": "почини валидатор"})
    worker = make_worker(db_factory, llm, client_factory)

    run_id = await worker.claim()
    assert run_id == run.id
    await worker.execute(run_id)

    rows = await runs(db_factory)
    assert [(r.kind, r.status) for r in rows] == [("chat", "done"), ("build", "queued")]
    assert rows[1].parent_run_id == run.id

    await worker.execute(await worker.claim())
    rows = await runs(db_factory)
    assert rows[1].status == "done" and rows[1].result["state"] == "READY"


async def test_one_run_per_session_at_a_time(db_factory, db, session_row, llm, client_factory, backend):
    other_problem = backend.add_problem("other")
    other = AuthoringSession(user_id=USER_ID, polygon_id=other_problem.id, model="m", settings={})
    db.add(other)
    await db.commit()
    first = await enqueue(db, session_row, "build")
    await enqueue(db, session_row, "build")
    third = await enqueue(db, other, "build")
    worker = make_worker(db_factory, llm, client_factory)

    assert await worker.claim() == first.id
    assert await worker.claim() == third.id
    assert await worker.claim() is None


async def test_failed_run_reports_error(db_factory, db, session_row, llm, client_factory, backend, problem):
    backend.fail_paths[f"/polygon/problems/{problem.id}/info"] = (401, "Polygon API is not configured")
    await enqueue(db, session_row, "chat", {"text": "привет"})
    worker = make_worker(db_factory, llm, client_factory)
    await worker.execute(await worker.claim())

    rows = await runs(db_factory)
    assert rows[0].status == "failed" and "not configured" in rows[0].error
    async with db_factory() as s:
        last = (await s.execute(select(Message).order_by(Message.id.desc()))).scalars().first()
    assert last.meta["is_error"] and "Polygon API is not configured" in last.content


async def test_cancel_running_run(db_factory, db, session_row, llm, client_factory):
    run = await enqueue(db, session_row, "chat", {"text": "x"})
    run.cancel_requested = True
    await db.commit()
    worker = make_worker(db_factory, llm, client_factory)
    await worker.execute(await worker.claim())
    rows = await runs(db_factory)
    assert rows[0].status == "cancelled"


async def test_recover_marks_stale_runs_failed(db_factory, db, session_row, llm, client_factory):
    run = await enqueue(db, session_row, "generate", {"idea": "x"})
    run.status = "running"
    run.heartbeat_at = utcnow() - timedelta(hours=1)
    fresh = await enqueue(db, session_row, "build")
    fresh.status = "running"
    fresh.heartbeat_at = utcnow()
    await db.commit()
    worker = make_worker(db_factory, llm, client_factory)
    assert await worker.recover() == 1
    rows = {r.id: r for r in await runs(db_factory)}
    assert rows[run.id].status == "failed" and rows[fresh.id].status == "running"


async def test_scheduler_syncs_recent_idle_sessions(db_factory, db, session_row, llm, client_factory, backend,
                                                    problem):
    worker = make_worker(db_factory, llm, client_factory)
    assert await worker.scheduler_tick() == 1  # first snapshot
    assert await worker.scheduler_tick() == 0  # synced just now

    async with db_factory() as s:
        row = await s.get(AuthoringSession, session_row.id)
        row.last_synced_at = utcnow() - timedelta(hours=1)
        await s.commit()
    problem.tags = ["new"]
    assert await worker.scheduler_tick() == 1
    async with db_factory() as s:
        events = (await s.execute(select(Event))).scalars().all()
    assert [e.title for e in events] == ["теги: new"]

    # a session with a running operation is left alone
    async with db_factory() as s:
        row = await s.get(AuthoringSession, session_row.id)
        row.last_synced_at = utcnow() - timedelta(hours=1)
        await s.commit()
    await enqueue(db, session_row, "build")
    assert await worker.scheduler_tick() == 0

    # a session not opened for long is not synced
    async with db_factory() as s:
        row = await s.get(AuthoringSession, session_row.id)
        row.last_opened_at = utcnow() - timedelta(days=3)
        await s.commit()
    assert await worker.scheduler_tick() == 0


async def test_restart_fails_runs_with_fresh_heartbeat(db_factory, db, session_row, llm, client_factory):
    run = await enqueue(db, session_row, "chat", {"text": "x"})
    run.status, run.heartbeat_at = "running", utcnow()
    queued = await enqueue(db, session_row, "build")
    await db.commit()
    worker = make_worker(db_factory, llm, client_factory)
    assert await worker.recover() == 0          # periodic sweep: heartbeat is fresh
    assert await worker.recover(all_running=True) == 1  # start-up: nobody runs it any more
    assert await worker.claim() == queued.id


async def test_auto_build_off_is_respected_for_all_runs(db_factory, db, session_row, llm, client_factory, backend,
                                                        problem):
    from tests.test_groups import PLAN
    session_row.settings = {"auto_build": False}
    await db.commit()
    llm.on("Обнови валидатор", '<file role="validator" name="v.cpp">int main(){}</file>')
    llm.on("Напиши генератор тестов", '<file role="generator" name="x.cpp">int main(){}</file>')
    await enqueue(db, session_row, "groups", {"plan": PLAN})
    worker = make_worker(db_factory, llm, client_factory)
    await worker.execute(await worker.claim())
    assert [(r.kind, r.status) for r in await runs(db_factory)] == [("groups", "done")]


async def test_own_edits_are_not_announced_later(db_factory, db, session_row, llm, client_factory, problem):
    llm.on("маршрутизатор", json.dumps({"intent": "modify", "targets": ["statement"]}))
    llm.on("Ты вносишь изменения", '<statement lang="russian" field="legend">new</statement>')
    session_row.settings = {"auto_build": False}
    await db.commit()
    await enqueue(db, session_row, "chat", {"text": "перепиши легенду"})
    worker = make_worker(db_factory, llm, client_factory)
    await worker.execute(await worker.claim())
    async with db_factory() as s:
        row = await s.get(AuthoringSession, session_row.id)
        row.last_synced_at = utcnow() - timedelta(hours=1)
        await s.commit()
    await worker.scheduler_tick()
    async with db_factory() as s:
        assert (await s.execute(select(Event))).scalars().all() == []
