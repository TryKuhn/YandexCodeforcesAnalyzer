import jwt
import pytest

from authoring.models import Event, Snapshot
from authoring.polygon.client import PolygonError
from authoring.settings import settings
from authoring.sync.diff import diff, summarize
from authoring.sync.dossier import build_dossier
from authoring.sync.service import sync_session
from authoring.sync.snapshot import SnapshotError, file_role, script_generators, take_snapshot
from tests.conftest import USER_ID


def fill(backend, problem):
    problem.statements = {"russian": {"name": "A+B", "legend": "Сложите $a$ и $b$.", "input": "a b", "output": "a+b"}}
    problem.tags = ["math"]
    backend.put_file(problem, "resource", "testlib.h", "// huge")
    backend.put_file(problem, "source", "gen.cpp", "int main(){}\n")
    backend.put_file(problem, "source", "val.cpp", "validator\n")
    problem.validator = "val.cpp"
    problem.checker = "std::ncmp.cpp"
    problem.solutions["main.cpp"] = {"content": "main\n", "tag": "MA", "mtime": backend.tick()}
    problem.tests[1] = {"index": 1, "manual": True, "input": "1 2\n", "group": None, "points": None,
                        "useInStatements": True, "scriptLine": None, "description": None}
    problem.script = "gen 1 > $\n"
    backend.route("POST", f"/polygon/problems/{problem.id}/script/tests", {"source": problem.script}, {})


async def test_client_sends_minted_user_token(backend, client_factory, problem):
    seen = {}
    original = backend.handle

    def spy(request):
        seen["auth"] = request.headers["Authorization"]
        return original(request)

    backend.handle = spy  # type: ignore[method-assign]
    await client_factory(USER_ID).info(problem.id)
    payload = jwt.decode(seen["auth"].split()[1], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["user_id"] == USER_ID and payload["svc"] == "ai-authoring"


async def test_client_raises_backend_detail(backend, client_factory, problem):
    backend.fail_paths[f"/polygon/problems/{problem.id}/info"] = (401, "Polygon API is not configured")
    with pytest.raises(PolygonError) as e:
        await client_factory(USER_ID).info(problem.id)
    assert e.value.status == 401 and e.value.message == "Polygon API is not configured"


async def test_snapshot_reads_everything_and_reuses_unchanged_content(backend, client_factory, problem):
    fill(backend, problem)
    client = client_factory(USER_ID)
    first = await take_snapshot(client, problem.id)
    assert first["files"]["resource/testlib.h"]["content"] is None
    assert first["files"]["resource/testlib.h"]["skipped"] == "standard"
    assert first["files"]["source/gen.cpp"]["content"] == "int main(){}\n"
    assert first["solutions"]["main.cpp"]["content"] == "main\n"
    assert first["samples"] == {"1": "1 2\n"}
    assert [t["index"] for t in first["tests"]] == [1, 2]
    assert first["validator"] == "val.cpp" and first["errors"] == []

    backend.calls.clear()
    second = await take_snapshot(client, problem.id, first)
    content_calls = [c for c in backend.calls if c[1].endswith("/content")]
    assert content_calls == []
    assert second["files"]["source/gen.cpp"]["content"] == "int main(){}\n"

    backend.put_file(problem, "source", "gen.cpp", "int main(){return 0;}\n")
    backend.calls.clear()
    third = await take_snapshot(client, problem.id, second)
    assert [c for c in backend.calls if c[1].endswith("/files/content")] == [
        ("GET", f"/polygon/problems/{problem.id}/files/content")]
    assert third["files"]["source/gen.cpp"]["content"] == "int main(){return 0;}\n"


async def test_snapshot_fails_without_access(backend, client_factory, problem):
    backend.fail_paths[f"/polygon/problems/{problem.id}/info"] = (403, "no access")
    with pytest.raises(SnapshotError, match="no access"):
        await take_snapshot(client_factory(USER_ID), problem.id)


async def test_partial_failures_are_recorded(backend, client_factory, problem):
    backend.fail_paths[f"/polygon/problems/{problem.id}/script"] = (500, "boom")
    snap = await take_snapshot(client_factory(USER_ID), problem.id)
    assert snap["script"] == "" and snap["errors"] == ["script: boom"]


async def test_roles_and_generators(backend, client_factory, problem):
    fill(backend, problem)
    snap = await take_snapshot(client_factory(USER_ID), problem.id)
    assert script_generators("<#list 1..3 as i>\ngen_a 1 ${i} > $\n</#list>\ngen_b > $\n") == ["gen_a", "gen_b"]
    assert file_role(snap, snap["files"]["source/gen.cpp"]) == "generator"
    assert file_role(snap, snap["files"]["source/val.cpp"]) == "validator"


def test_diff_reports_user_visible_changes():
    old = {
        "info": {"timeLimit": 1000, "memoryLimit": 256},
        "statements": {"russian": {"legend": "a", "input": "x"}},
        "tags": ["a"],
        "checker": "std::wcmp.cpp",
        "files": {"source/gen.cpp": {"type": "source", "name": "gen.cpp", "mtime": 1, "length": 3, "content": "abc"},
                  "source/old.cpp": {"type": "source", "name": "old.cpp", "mtime": 1, "length": 1}},
        "solutions": {"main.cpp": {"tag": "MA", "mtime": 1, "length": 1, "content": "a"}},
        "script": "gen 1 > $",
        "tests": [{"index": 1}],
        "groups": [],
        "packages": [{"id": 5, "state": "RUNNING"}],
    }
    new = {
        "info": {"timeLimit": 2000, "memoryLimit": 256},
        "statements": {"russian": {"legend": "b", "input": "x"}, "english": {"legend": "c"}},
        "tags": ["a", "b"],
        "checker": "check.cpp",
        "script": "gen gen 1 > $\ngen 2 > $",
        "files": {"source/gen.cpp": {"type": "source", "name": "gen.cpp", "mtime": 2, "length": 3, "content": "abd"},
                  "source/new.cpp": {"type": "source", "name": "new.cpp", "mtime": 2, "length": 1}},
        "solutions": {"main.cpp": {"tag": "OK", "mtime": 1, "length": 1, "content": "a"},
                      "wa.cpp": {"tag": "WA", "mtime": 2, "length": 1}},
        "tests": [{"index": 1, "group": "1"}, {"index": 2, "group": "1"}],
        "groups": [{"name": "1", "pointsPolicy": "COMPLETE_GROUP", "feedbackPolicy": "ICPC", "dependencies": []}],
        "packages": [{"id": 5, "state": "FAILED"}, {"id": 6, "revision": 3, "state": "READY"}],
    }
    texts = [c["text"] for c in diff(old, new)]
    assert "TL: 1000 мс → 2000 мс" in texts
    assert "условие (russian): легенда" in texts
    assert "добавлено условие (english)" in texts
    assert "теги: a, b" in texts
    assert "чекер: std::wcmp.cpp → check.cpp" in texts
    assert "изменён генератор gen.cpp" in texts
    assert "удалён файл old.cpp" in texts
    assert "добавлен исходник new.cpp" in texts
    assert "решение main.cpp: тег MA → OK" in texts
    assert "добавлено решение wa.cpp (WA)" in texts
    assert "изменён скрипт генерации тестов" in texts
    assert "тестов: 1 → 2" in texts
    assert "изменены группы тестов (1: 2 т.)" in texts
    assert "пакет #5: ошибка сборки" in texts
    assert "новый пакет #6 (rev. 3): собран" in texts
    assert diff(new, new) == []
    assert summarize([{"text": "a"}, {"text": "b"}, {"text": "c"}, {"text": "d"}]) == "a; b; c и ещё 1"


async def test_sync_session_announces_only_external_changes(db, session_row, backend, client_factory, problem):
    fill(backend, problem)
    client = client_factory(USER_ID)
    snap, event = await sync_session(db, session_row, client)
    assert event is None  # nothing to compare with yet
    assert (await db.get(Snapshot, session_row.id)) is not None

    problem.info["timeLimit"] = 3000
    _, event = await sync_session(db, session_row, client)
    assert event is not None and event.source == "polygon" and "TL" in event.title

    problem.info["timeLimit"] = 4000
    _, event = await sync_session(db, session_row, client, announce=False)
    assert event is None
    events = (await db.execute(Event.__table__.select())).all()
    assert len(events) == 1
    assert session_row.last_synced_at is not None


async def test_dossier_contains_materials(backend, client_factory, problem):
    fill(backend, problem)
    snap = await take_snapshot(client_factory(USER_ID), problem.id)
    text = build_dossier(snap, polygon_id=problem.id, problem_type="regular")
    assert f"# Задача Polygon #{problem.id}" in text
    assert "Сложите $a$ и $b$." in text
    assert "### gen.cpp — generator (source)" in text
    assert "### main.cpp [MA]" in text
    assert "testlib.h (resource, standard)" in text
    assert "Из скрипта: 2." in text
    assert "```\n1 2\n```" in text
