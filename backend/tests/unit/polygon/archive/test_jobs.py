"""Unit tests for api.user.polygon.archive.jobs (in-memory job store)."""
from __future__ import annotations

import pytest

import api.user.polygon.archive.jobs as J
from api.user.polygon.archive.jobs import (
    ImportJob,
    ProblemStatus,
    create_job,
    get_job,
)


@pytest.fixture(autouse=True)
def clean_jobs():
    """Each test gets an empty JOBS registry and a restored MAX_JOBS."""
    saved = dict(J.JOBS)
    saved_max = J.MAX_JOBS
    J.JOBS.clear()
    yield
    J.JOBS.clear()
    J.JOBS.update(saved)
    J.MAX_JOBS = saved_max


def test_problem_status_note_and_to_dict():
    ps = ProblemStatus(name="A", polygon_name="x1")
    for i in range(25):
        ps.note(f"msg{i}")
    d = ps.to_dict()
    # log truncated to last 20
    assert d["log"] == [f"msg{i}" for i in range(5, 25)]
    assert d["name"] == "A"
    assert d["polygon_name"] == "x1"
    assert d["stage"] == "wait"


def test_import_job_to_dict_includes_problems():
    job = ImportJob(id="j1", user_id=7, archive_name="a.zip", prefix="p")
    job.problems = [ProblemStatus(name="A", polygon_name="p1")]
    d = job.to_dict()
    assert d["job_id"] == "j1"
    assert d["status"] == "parsing"
    assert d["archive_name"] == "a.zip"
    assert d["prefix"] == "p"
    assert "created_at" in d
    assert len(d["problems"]) == 1
    assert d["problems"][0]["name"] == "A"


def test_create_job_registers_and_returns():
    job = create_job(user_id=3, archive_name="x.zip")
    assert job.id in J.JOBS
    assert job.user_id == 3
    assert job.archive_name == "x.zip"
    assert job.status == "parsing"


def test_create_job_evicts_oldest_over_limit():
    J.MAX_JOBS = 3
    jobs = [create_job(user_id=1, archive_name=f"a{i}.zip") for i in range(3)]
    # bump created_at so eviction order is deterministic (oldest first)
    import datetime

    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    for i, j in enumerate(jobs):
        j.created_at = base + datetime.timedelta(seconds=i)

    new = create_job(user_id=1, archive_name="new.zip")
    assert len(J.JOBS) == 3
    # the oldest (jobs[0]) was evicted; the rest remain
    assert jobs[0].id not in J.JOBS
    assert jobs[1].id in J.JOBS
    assert new.id in J.JOBS


def test_get_job_owner_check():
    job = create_job(user_id=10, archive_name="a.zip")
    assert get_job(job.id, 10) is job
    # wrong owner -> None
    assert get_job(job.id, 999) is None
    # unknown id -> None
    assert get_job("nope", 10) is None
