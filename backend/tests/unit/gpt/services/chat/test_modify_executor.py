"""Unit tests for the modify executor (services.chat.modify_executor).

Collaborators are imported as module objects into the modify_executor namespace,
so we monkeypatch their functions there (e.g. ``modify_executor.statement_gen``).
All generation/sync side-effects are faked; we assert the returned dict shapes.
"""
import pytest

from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.chat import modify_executor as me
from api.user.gpt.services.chat.context_resolver import ResolvedContext

MOD = "api.user.gpt.services.chat.modify_executor"


# ── pure helpers ─────────────────────────────────────────────────────────────
def test_label_known_and_unknown():
    assert me._label("checker") == "checker.cpp"
    assert me._label("solution_py") == "solution.py"
    assert me._label("script") == "script.txt"
    # unknown key passes through unchanged
    assert me._label("mystery") == "mystery"


def test_file_labels_cover_valid_types():
    assert me._VALID_FILE_TYPES == set(me._FILE_LABELS)
    for key in ("validator", "generator", "checker", "interactor", "scorer",
                "jury_answer", "solution_cpp", "solution_py"):
        assert key in me._FILE_LABELS


def test_groups_enabled(task_session):
    task_session.problem_settings = {}
    assert me._groups_enabled(task_session) is False
    task_session.problem_settings = {"enable_groups": True}
    assert me._groups_enabled(task_session) is True
    task_session.problem_settings = {"enable_points": True}
    assert me._groups_enabled(task_session) is True
    task_session.problem_settings = None
    assert me._groups_enabled(task_session) is False


# ── helpers to stub collaborators ────────────────────────────────────────────
def _stub_statement_gen(monkeypatch, result):
    async def fake(**kwargs):
        return result
    monkeypatch.setattr(f"{MOD}.statement_gen.generate", fake)


def _stub_statement_sync(monkeypatch):
    calls = []

    async def fake(db, session, stmt):
        calls.append(stmt)
    monkeypatch.setattr(f"{MOD}.statement_sync.sync_statement", fake)
    return calls


def _stub_sync_files(monkeypatch, returns=None):
    captured = {}

    async def fake(db, session, items):
        captured["items"] = list(items)
        # default: report every file_type as synced
        return returns if returns is not None else [k for k, _ in items]
    monkeypatch.setattr(f"{MOD}.file_sync.sync_files", fake)
    return captured


# ── _modify_statement (statement scope) ──────────────────────────────────────
@pytest.mark.asyncio
async def test_modify_statement_cosmetic_no_cascade(db, task_session, monkeypatch):
    task_session.statement = {"name": "old"}
    await db.commit()

    _stub_statement_gen(monkeypatch, {"name": "new"})
    _stub_statement_sync(monkeypatch)

    async def fake_essence(old, new):
        return {"essence_changed": False, "dependents": [], "reason": ""}
    monkeypatch.setattr(f"{MOD}.essence_checker.check", fake_essence)

    out = await me.execute(db, task_session, "fix typo",
                           ResolvedContext(scope="statement"))
    assert out["synced"] is True
    assert out["updated_files"] == []
    assert out["statement"] == {"name": "new"}
    assert "Обновил условие" in out["response"]
    # session statement persisted
    assert task_session.statement == {"name": "new"}


@pytest.mark.asyncio
async def test_modify_statement_carries_over_sections(db, task_session, monkeypatch):
    task_session.statement = {"name": "old", "scoring": "S", "interaction": "I"}
    await db.commit()

    _stub_statement_gen(monkeypatch, {"name": "new"})  # drops scoring/interaction
    _stub_statement_sync(monkeypatch)

    async def fake_essence(old, new):
        return {"essence_changed": False, "dependents": [], "reason": ""}
    monkeypatch.setattr(f"{MOD}.essence_checker.check", fake_essence)

    out = await me.execute(db, task_session, "tweak",
                           ResolvedContext(scope="statement"))
    assert out["statement"]["scoring"] == "S"
    assert out["statement"]["interaction"] == "I"


@pytest.mark.asyncio
async def test_modify_statement_essence_cascade(db, task_session, monkeypatch):
    task_session.statement = {"name": "old"}
    await upsert_ai_file(db, task_session.id, "validator", "old-v")
    await upsert_ai_file(db, task_session.id, "checker", "old-c")
    await db.commit()

    _stub_statement_gen(monkeypatch, {"name": "new"})
    _stub_statement_sync(monkeypatch)

    async def fake_essence(old, new):
        # checker exists, ghost does not → only validator+checker eligible
        return {"essence_changed": True,
                "dependents": ["validator", "ghost"], "reason": "constraints"}
    monkeypatch.setattr(f"{MOD}.essence_checker.check", fake_essence)

    regen_calls = []

    async def fake_regenerate(ft, stmt, model, interactive, problem_type=None):
        regen_calls.append(ft)
        return f"new-{ft}"
    monkeypatch.setattr(f"{MOD}.file_gen.regenerate", fake_regenerate)

    captured = _stub_sync_files(monkeypatch)

    out = await me.execute(db, task_session, "change n",
                           ResolvedContext(scope="statement"))
    # only validator regenerated (ghost not in existing)
    assert regen_calls == ["validator"]
    assert out["updated_files"] == ["validator"]
    assert "зависимые файлы" in out["response"]
    assert captured["items"] == [("validator", "new-validator")]


# ── _modify_file (file scope) ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_modify_file_refine_existing(db, task_session, monkeypatch):
    await upsert_ai_file(db, task_session.id, "checker", "existing code")
    await db.commit()

    async def fake_refine(**kwargs):
        assert kwargs["file_type"] == "checker"
        assert kwargs["current_code"] == "existing code"
        return "refined code"
    monkeypatch.setattr(f"{MOD}.file_gen.refine", fake_refine)

    sync_calls = {}

    async def fake_sync_file(db_, session, key, code):
        sync_calls["key"] = key
        sync_calls["code"] = code
    monkeypatch.setattr(f"{MOD}.file_sync.sync_file", fake_sync_file)

    out = await me.execute(db, task_session, "improve it",
                           ResolvedContext(scope="file", file_key="checker"))
    assert out["updated_files"] == ["checker"]
    assert out["technical_data"] == {"checker": "refined code"}
    assert out["synced"] is True
    assert "обновлён" in out["response"]
    assert sync_calls == {"key": "checker", "code": "refined code"}


@pytest.mark.asyncio
async def test_modify_file_generate_when_absent(db, task_session, monkeypatch):
    # No file in db → generate-from-scratch branch
    async def fake_generate(file_key, statement, model, interactive, problem_type=None):
        return "fresh code"
    monkeypatch.setattr(f"{MOD}.file_gen.generate", fake_generate)

    async def fake_sync_file(db_, session, key, code):
        pass
    monkeypatch.setattr(f"{MOD}.file_sync.sync_file", fake_sync_file)

    out = await me.execute(db, task_session, "create checker",
                           ResolvedContext(scope="file", file_key="checker"))
    assert out["technical_data"] == {"checker": "fresh code"}
    assert "сгенерирован" in out["response"]


# ── _modify_task (task scope) ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_modify_task_empty_statement_generates_from_scratch(db, task_session, monkeypatch):
    task_session.statement = None
    await db.commit()

    _stub_statement_gen(monkeypatch, {"name": "Brand New"})
    _stub_statement_sync(monkeypatch)
    _stub_sync_files(monkeypatch)

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        return {"checker": "c", "validator": "v"}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    out = await me.execute(db, task_session, "make a task",
                           ResolvedContext(scope="task"))
    assert out["statement"] == {"name": "Brand New"}
    assert "statement" in out["updated_files"]
    assert "checker" in out["updated_files"] and "validator" in out["updated_files"]
    assert out["build"] is True
    assert "Создал" in out["response"]


@pytest.mark.asyncio
async def test_modify_task_statement_but_no_files_generates_pack(db, task_session, monkeypatch):
    task_session.statement = {"name": "Has Statement"}
    await db.commit()  # no files in db

    _stub_sync_files(monkeypatch)

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        return {"checker": "c"}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    out = await me.execute(db, task_session, "generate files",
                           ResolvedContext(scope="task"))
    assert out["updated_files"] == ["checker"]
    assert out["build"] is True
    assert "Сгенерированы" in out["response"]


@pytest.mark.asyncio
async def test_modify_task_picks_and_rewrites_files(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    await upsert_ai_file(db, task_session.id, "checker", "old checker")
    await db.commit()

    async def fake_ask(model, messages, json_mode=True):
        # returns updated checker (existing) + new solution_cpp (valid type)
        return {"checker": "new checker", "solution_cpp": "sol", "junk": 123}
    monkeypatch.setattr(f"{MOD}.llm.ask", fake_ask)

    captured = _stub_sync_files(monkeypatch)

    out = await me.execute(db, task_session, "fix checker and add solution",
                           ResolvedContext(scope="task"))
    keys = {k for k, _ in captured["items"]}
    assert keys == {"checker", "solution_cpp"}
    assert set(out["updated_files"]) == {"checker", "solution_cpp"}
    assert out["technical_data"]["checker"] == "new checker"
    assert "junk" not in out["technical_data"]
    assert out["synced"] is True


@pytest.mark.asyncio
async def test_modify_task_llm_error_returns_unsynced(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    async def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(f"{MOD}.llm.ask", boom)

    out = await me.execute(db, task_session, "do something",
                           ResolvedContext(scope="task"))
    assert out["synced"] is False
    assert out["updated_files"] == []
    assert "Не понял запрос" in out["response"]


@pytest.mark.asyncio
async def test_modify_task_nothing_changed(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    async def fake_ask(model, messages, json_mode=True):
        return {"checker": "   ", "ghost": "x"}  # empty content / invalid key
    monkeypatch.setattr(f"{MOD}.llm.ask", fake_ask)

    out = await me.execute(db, task_session, "noop",
                           ResolvedContext(scope="task"))
    assert out["synced"] is False
    assert out["updated_files"] == []
    assert "Не нашёл, что изменить" in out["response"]


# ── regenerate (public entry) ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_regenerate_redo_when_statement_present(db, task_session, monkeypatch):
    task_session.statement = {"name": "old"}
    await db.commit()

    _stub_statement_gen(monkeypatch, {"name": "redone"})
    _stub_statement_sync(monkeypatch)
    _stub_sync_files(monkeypatch)

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        return {"checker": "c"}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    out = await me.regenerate(db, task_session, "redo it")
    assert "Пересоздал" in out["response"]
    assert out["statement"] == {"name": "redone"}


# ── _generate_pack with groups / subtasks ────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_pack_empty_pack(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    await db.commit()

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        return {}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    out = await me._generate_pack(db, task_session)
    assert out["synced"] is False
    assert out["updated_files"] == []
    assert "Не удалось сгенерировать" in out["response"]


@pytest.mark.asyncio
async def test_generate_pack_reports_failed_syncs(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    await db.commit()

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        return {"checker": "c", "validator": "v"}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    # only checker syncs; validator fails
    async def fake_sync_files(db_, session, items):
        return ["checker"]
    monkeypatch.setattr(f"{MOD}.file_sync.sync_files", fake_sync_files)

    out = await me._generate_pack(db, task_session)
    assert out["updated_files"] == ["checker"]
    assert "Не удалось синхронизировать" in out["response"]
    assert "validator.cpp" in out["response"]


@pytest.mark.asyncio
async def test_generate_pack_with_subtasks_adds_partials(db, task_session, monkeypatch):
    task_session.statement = {"name": "S"}
    task_session.problem_settings = {"enable_groups": True, "subtasks": [{"i": 1}]}
    await db.commit()

    pack_subtasks = {}

    async def fake_pack(problem_type, stmt, model, subtasks=None):
        pack_subtasks["v"] = subtasks
        return {"checker": "c"}, {}
    monkeypatch.setattr(f"{MOD}.file_gen.generate_pack", fake_pack)

    async def fake_partials(stmt, model, subtasks, problem_type=None):
        return [{"file_type": "wa_sol", "code": "wa", "tag": "WA", "name": "wa1"}], {}
    monkeypatch.setattr(f"{MOD}.subtask_solutions_gen.generate", fake_partials)

    captured = _stub_sync_files(monkeypatch)

    await me._generate_pack(db, task_session)
    # subtasks forwarded to generate_pack
    assert pack_subtasks["v"] == [{"i": 1}]
    # partial solution merged into pack and synced
    keys = {k for k, _ in captured["items"]}
    assert {"checker", "wa_sol"} <= keys
    assert task_session.solution_meta["wa_sol"] == {"tag": "WA", "name": "wa1"}


# ── _prepare_subtasks ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prepare_subtasks_noop_without_groups(db, task_session, monkeypatch):
    task_session.problem_settings = {}
    await db.commit()
    stmt = {"name": "S"}
    out = await me._prepare_subtasks(db, task_session, stmt)
    assert out is stmt  # unchanged object returned


@pytest.mark.asyncio
async def test_prepare_subtasks_renders_scoring(db, task_session, monkeypatch):
    task_session.problem_settings = {"enable_groups": True}
    await db.commit()

    async def fake_plan(stmt, model):
        return [{"points": 50}, {"points": 50}]
    monkeypatch.setattr(f"{MOD}.subtask_plan_gen.generate", fake_plan)
    monkeypatch.setattr(f"{MOD}.subtask_plan_gen.render_scoring_latex",
                        lambda subtasks: "SCORING-TABLE")
    _stub_statement_sync(monkeypatch)

    out = await me._prepare_subtasks(db, task_session, {"name": "S"})
    assert out["scoring"] == "SCORING-TABLE"
    assert task_session.problem_settings["subtasks"] == [{"points": 50}, {"points": 50}]
    assert task_session.problem_settings["enable_points"] is True


# ── _prepare_samples ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_prepare_samples_uploads_examples(db, task_session, monkeypatch):
    task_session.problem_settings = {}
    await db.commit()

    async def fake_gen(stmt, model, count=3):
        return [{"input": "1", "output": "2"}, {"input": "3", "output": "4"}]
    monkeypatch.setattr(f"{MOD}.samples_gen.generate", fake_gen)

    async def fake_ensure_problem(db_, session):
        return 777
    monkeypatch.setattr(f"{MOD}.file_sync.ensure_problem", fake_ensure_problem)

    upload_args = {}

    async def fake_upload(db_, problem_id, user_id, indexed, group=None):
        upload_args["problem_id"] = problem_id
        upload_args["indexed"] = indexed
        upload_args["group"] = group
    monkeypatch.setattr(f"{MOD}.samples_sync.upload_examples", fake_upload)

    await me._prepare_samples(db, task_session, {"name": "S"})
    assert task_session.examples == [
        {"index": 1, "input": "1", "output": "2"},
        {"index": 2, "input": "3", "output": "4"},
    ]
    assert upload_args["problem_id"] == 777
    assert upload_args["group"] is None  # groups disabled


@pytest.mark.asyncio
async def test_prepare_samples_group_zero_when_groups_enabled(db, task_session, monkeypatch):
    task_session.problem_settings = {"enable_groups": True}
    await db.commit()

    async def fake_gen(stmt, model, count=3):
        return [{"input": "1", "output": "2"}]
    monkeypatch.setattr(f"{MOD}.samples_gen.generate", fake_gen)

    async def fake_ensure_problem(db_, session):
        return 1
    monkeypatch.setattr(f"{MOD}.file_sync.ensure_problem", fake_ensure_problem)

    upload_args = {}

    async def fake_upload(db_, problem_id, user_id, indexed, group=None):
        upload_args["group"] = group
    monkeypatch.setattr(f"{MOD}.samples_sync.upload_examples", fake_upload)

    await me._prepare_samples(db, task_session, {"name": "S"})
    assert upload_args["group"] == "0"


@pytest.mark.asyncio
async def test_prepare_samples_noop_when_no_examples(db, task_session, monkeypatch):
    async def fake_gen(stmt, model, count=3):
        return []
    monkeypatch.setattr(f"{MOD}.samples_gen.generate", fake_gen)

    called = {"upload": False}

    async def fake_upload(*a, **k):
        called["upload"] = True
    monkeypatch.setattr(f"{MOD}.samples_sync.upload_examples", fake_upload)

    await me._prepare_samples(db, task_session, {"name": "S"})
    assert called["upload"] is False


@pytest.mark.asyncio
async def test_prepare_samples_swallows_generation_error(db, task_session, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("gen down")
    monkeypatch.setattr(f"{MOD}.samples_gen.generate", boom)
    # must not raise
    await me._prepare_samples(db, task_session, {"name": "S"})
