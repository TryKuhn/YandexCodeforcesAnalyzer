"""Unit tests for Polygon-problem import (services.import_session).

All Polygon wrapper calls are imported by name into the module under test, so we
monkeypatch them in that namespace with async fakes. The real ``db`` fixture and
``upsert_ai_file`` are used so generated-file rows are actually persisted.
"""
import pytest
from sqlalchemy import select

from api.user.gpt.services import import_session as imp
from models.task.generated_file import TaskGeneratedFile
from models.task.session import PipelineStage, ProblemType, TaskSession


# ── pure helper: _extract_statement ─────────────────────────────────────────

def test_extract_statement_prefers_russian():
    raw = {
        "russian": {"name": "Имя", "legend": "ru-leg", "input": "in", "output": "out"},
        "english": {"name": "Name"},
    }
    out = imp._extract_statement(raw)
    assert out["name"] == "Имя"
    assert out["legend"] == "ru-leg"
    assert out["notes"] == "" and out["tutorial"] == ""


def test_extract_statement_falls_back_to_english_then_first():
    out = imp._extract_statement({"english": {"name": "Eng"}})
    assert out["name"] == "Eng"
    out2 = imp._extract_statement({"de": {"name": "First"}})
    assert out2["name"] == "First"


def test_extract_statement_non_dict_returns_blank():
    out = imp._extract_statement("garbage")
    assert out == {"name": "", "legend": "", "input": "", "output": "",
                   "notes": "", "tutorial": ""}


# ── shared fakes / patch helper ─────────────────────────────────────────────

def _patch(monkeypatch, **overrides):
    """Install async fakes for every Polygon wrapper used by import_session.

    Defaults make every loader return empty; pass overrides as plain values or
    callables. ``info`` and ``statements`` are special-cased below.
    """
    async def _const(value):
        return value

    def mk(value):
        async def _f(*a, **kw):
            if callable(value):
                return value(*a, **kw)
            return value
        return _f

    defaults = {
        "get_statements": {"russian": {"name": "P", "legend": "L"}},
        "get_problem_info": {},
        "view_tags": [],
        "get_files": {"sourceFiles": []},
        "view_file": "",
        "get_solutions": [],
        "view_solution": "",
        "get_script": "",
        "get_tests": [],
        "get_test_input": "",
    }
    defaults.update(overrides)
    for name, val in defaults.items():
        monkeypatch.setattr(imp, name, mk(val))


# ── import_full: mapping + branches ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_full_regular_mapping(db, user, monkeypatch):
    _patch(monkeypatch,
           get_problem_info={"inputFile": "in.txt", "outputFile": "out.txt",
                             "interactive": False, "timeLimit": 1000,
                             "memoryLimit": 512},
           view_tags=["dp", "math"])
    res = await imp.import_full(db, user.id, 777, "mymodel", load_files=False)

    assert res["problem_type"] == ProblemType.REGULAR
    assert res["stage"] == PipelineStage.STATEMENT
    assert res["polygon_problem_id"] == 777
    ps = res["problem_settings"]
    assert ps["input_file"] == "in.txt"
    assert ps["output_file"] == "out.txt"
    assert ps["interactive"] is False
    assert ps["time_limit"] == 1000
    assert ps["memory_limit"] == 512
    assert ps["tags"] == ["dp", "math"]
    assert res["statement"]["name"] == "P"

    # session persisted
    session = await db.get(TaskSession, res["session_id"])
    assert session is not None
    assert session.user_id == user.id
    assert session.problem_type == ProblemType.REGULAR


@pytest.mark.asyncio
async def test_import_full_interactive_maps_problem_type(db, user, monkeypatch):
    _patch(monkeypatch, get_problem_info={"interactive": True})
    res = await imp.import_full(db, user.id, 1, "m", load_files=False)
    assert res["problem_type"] == ProblemType.INTERACTIVE
    assert res["problem_settings"]["interactive"] is True


@pytest.mark.asyncio
async def test_import_full_defaults_when_info_fails(db, user, monkeypatch):
    _patch(monkeypatch)

    async def boom(*a, **kw):
        raise RuntimeError("polygon down")

    monkeypatch.setattr(imp, "get_problem_info", boom)
    res = await imp.import_full(db, user.id, 1, "m", load_files=False)
    ps = res["problem_settings"]
    assert ps["input_file"] == "stdin"
    assert ps["output_file"] == "stdout"
    assert ps["time_limit"] == 2000
    assert ps["memory_limit"] == 256
    assert res["problem_type"] == ProblemType.REGULAR


@pytest.mark.asyncio
async def test_import_full_tags_failure_leaves_empty(db, user, monkeypatch):
    _patch(monkeypatch)

    async def boom(*a, **kw):
        raise RuntimeError("no tags")

    monkeypatch.setattr(imp, "view_tags", boom)
    res = await imp.import_full(db, user.id, 1, "m", load_files=False)
    assert res["problem_settings"]["tags"] == []


# ── load_files branch: source files, solutions, script, examples ────────────

@pytest.mark.asyncio
async def test_import_full_loads_source_files(db, user, monkeypatch):
    _patch(monkeypatch,
           get_files={"sourceFiles": [
               {"name": "checker.cpp"},
               {"name": "validator.cpp"},
               {"name": "ignored.txt"},  # not in KNOWN_SOURCE_FILES
           ]},
           view_file=lambda problem_id, ftype, name, uid, db: f"// {name}")
    res = await imp.import_full(db, user.id, 9, "m", load_files=True)

    td = res["technical_data"]
    assert td["checker"] == "// checker.cpp"
    assert td["validator"] == "// validator.cpp"
    assert "ignored.txt" not in td

    files = (await db.execute(
        select(TaskGeneratedFile).where(
            TaskGeneratedFile.session_id == res["session_id"]))).scalars().all()
    types = {f.file_type for f in files}
    assert {"checker", "validator"} <= types


@pytest.mark.asyncio
async def test_import_full_loads_solutions_by_tag_and_custom(db, user, monkeypatch):
    _patch(monkeypatch,
           get_solutions=[
               {"name": "main.cpp", "tag": "MA"},
               {"name": "slow.cpp", "tag": "TL"},
               {"name": "weird.cpp", "tag": "XYZ"},  # unknown → custom
           ],
           view_solution=lambda problem_id, name, uid, db: f"code {name}")
    res = await imp.import_full(db, user.id, 3, "m", load_files=True)
    td = res["technical_data"]
    assert td["solution_cpp"] == "code main.cpp"
    assert td["tl_sol"] == "code slow.cpp"
    # the unknown tag produced a sol_custom_* key
    custom = [k for k in td if k.startswith("sol_custom_")]
    assert len(custom) == 1

    session = await db.get(TaskSession, res["session_id"])
    assert session.solution_meta
    meta = next(iter(session.solution_meta.values()))
    assert meta["tag"] == "XYZ"
    assert meta["name"] == "weird.cpp"


@pytest.mark.asyncio
async def test_import_full_solution_default_tag_ok(db, user, monkeypatch):
    # missing/empty tag defaults to OK → which is unknown in _TAG_TO_TYPE → custom
    _patch(monkeypatch,
           get_solutions=[{"name": "s.cpp"}],
           view_solution=lambda *a, **kw: "code")
    res = await imp.import_full(db, user.id, 3, "m", load_files=True)
    assert any(k.startswith("sol_custom_") for k in res["technical_data"])


@pytest.mark.asyncio
async def test_import_full_loads_script_and_examples(db, user, monkeypatch):
    _patch(monkeypatch,
           get_script="gen 1 > $",
           get_tests=[
               {"index": 1, "useInStatements": True},
               {"index": 2, "useInStatements": False},
           ],
           get_test_input=lambda problem_id, ts, idx, uid, db: f"input-{idx}")
    res = await imp.import_full(db, user.id, 4, "m", load_files=True)
    assert res["technical_data"]["script"] == "gen 1 > $"
    ex = res["examples"]
    assert len(ex) == 1
    assert ex[0]["index"] == 1
    assert ex[0]["input"] == "input-1"


@pytest.mark.asyncio
async def test_import_full_source_file_load_error_is_swallowed(db, user, monkeypatch):
    _patch(monkeypatch,
           get_files={"sourceFiles": [{"name": "checker.cpp"}]})

    async def boom(*a, **kw):
        raise RuntimeError("view failed")

    monkeypatch.setattr(imp, "view_file", boom)
    # should not raise; checker simply absent
    res = await imp.import_full(db, user.id, 5, "m", load_files=True)
    assert "checker" not in res["technical_data"]


@pytest.mark.asyncio
async def test_import_full_no_load_files_skips_artifacts(db, user, monkeypatch):
    called = {"files": False}

    async def track_get_files(*a, **kw):
        called["files"] = True
        return {"sourceFiles": []}

    _patch(monkeypatch)
    monkeypatch.setattr(imp, "get_files", track_get_files)
    res = await imp.import_full(db, user.id, 6, "m", load_files=False)
    assert called["files"] is False
    assert res["technical_data"] == {}
    assert res["examples"] == []
