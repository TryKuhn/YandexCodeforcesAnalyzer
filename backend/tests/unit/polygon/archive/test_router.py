"""Unit tests for api.user.polygon.archive.router endpoints.

The handlers are awaited directly with a fake ``UploadFile`` and dependency
values supplied positionally. ``get_user`` and the background ``run_import``
task are mocked so nothing touches the DB or the network.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import api.user.polygon.archive.router as R
from api.user.polygon.archive.jobs import ImportJob
from api.user.polygon.archive.router import (
    route_import_archive,
    route_import_status,
)

pytestmark = pytest.mark.asyncio


class _FakeUpload:
    def __init__(self, filename, data):
        self.filename = filename
        self._data = data

    async def read(self):
        return self._data


class _FakeUser:
    polygon_api_key = "k"
    polygon_api_secret = "s"


@pytest.fixture
def patched(monkeypatch):
    captured = {}

    async def fake_get_user(user_id, db):
        captured["user_id"] = user_id
        return _FakeUser()

    def fake_create_job(user_id, archive_name):
        job = ImportJob(id="job-xyz", user_id=user_id, archive_name=archive_name)
        captured["job"] = job
        return job

    def fake_create_task(coro):
        # close the coroutine so it isn't flagged as never-awaited
        coro.close()

        class _T:
            def add_done_callback(self, cb):
                pass

        return _T()

    monkeypatch.setattr(R, "get_user", fake_get_user)
    monkeypatch.setattr(R, "create_job", fake_create_job)
    monkeypatch.setattr(R.asyncio, "create_task", fake_create_task)
    return captured


async def test_import_archive_explicit_prefix(patched):
    file = _FakeUpload("Anything.zip", b"PK\x03\x04data")
    out = await route_import_archive(
        file=file,
        prefix="myprefix-",
        generate_ai=False,
        ai_model="m",
        build_package=False,
        user_id=42,
        db=None,
    )
    assert out == {"job_id": "job-xyz", "prefix": "myprefix-"}
    assert patched["job"].prefix == "myprefix-"
    assert patched["user_id"] == 42


async def test_import_archive_derives_prefix_from_filename(patched):
    file = _FakeUpload("2022-01-11-BelOI2022-stage3-day1.zip", b"data")
    out = await route_import_archive(
        file=file,
        prefix=None,
        generate_ai=True,
        ai_model="m",
        build_package=True,
        user_id=1,
        db=None,
    )
    assert out["prefix"] == "beloi22-1"


async def test_import_archive_rejects_non_zip(patched):
    file = _FakeUpload("archive.tar", b"data")
    with pytest.raises(HTTPException) as ei:
        await route_import_archive(
            file=file, prefix="p", generate_ai=False, ai_model="m",
            build_package=False, user_id=1, db=None,
        )
    assert ei.value.status_code == 400


async def test_import_archive_rejects_empty_file(patched):
    file = _FakeUpload("a.zip", b"")
    with pytest.raises(HTTPException) as ei:
        await route_import_archive(
            file=file, prefix="p", generate_ai=False, ai_model="m",
            build_package=False, user_id=1, db=None,
        )
    assert ei.value.status_code == 400


async def test_import_archive_rejects_too_large(patched, monkeypatch):
    monkeypatch.setattr(R, "MAX_ARCHIVE_SIZE", 4)
    file = _FakeUpload("a.zip", b"toolong")
    with pytest.raises(HTTPException) as ei:
        await route_import_archive(
            file=file, prefix="p", generate_ai=False, ai_model="m",
            build_package=False, user_id=1, db=None,
        )
    assert ei.value.status_code == 413


async def test_import_archive_unresolvable_prefix(patched):
    file = _FakeUpload("randomname.zip", b"data")
    with pytest.raises(HTTPException) as ei:
        await route_import_archive(
            file=file, prefix=None, generate_ai=False, ai_model="m",
            build_package=False, user_id=1, db=None,
        )
    assert ei.value.status_code == 400
    assert "префикс" in ei.value.detail


async def test_import_status_returns_job_dict(monkeypatch):
    job = ImportJob(id="j5", user_id=7, archive_name="a.zip")

    def fake_get_job(job_id, user_id):
        assert job_id == "j5" and user_id == 7
        return job

    monkeypatch.setattr(R, "get_job", fake_get_job)
    out = await route_import_status(job_id="j5", user_id=7)
    assert out["job_id"] == "j5"
    assert out["status"] == "parsing"


async def test_import_status_404(monkeypatch):
    monkeypatch.setattr(R, "get_job", lambda jid, uid: None)
    with pytest.raises(HTTPException) as ei:
        await route_import_status(job_id="missing", user_id=7)
    assert ei.value.status_code == 404
