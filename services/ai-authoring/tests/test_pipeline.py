import json

from sqlalchemy import select

from authoring.llm.protocol import FileEdit, LimitsEdit, StandardChecker, StatementEdit
from authoring.models import Build, Message
from authoring.pipeline.apply import apply_edits
from authoring.pipeline.build import run_build
from authoring.pipeline.chat import run_chat
from authoring.pipeline.generate import run_generate, run_groups
from tests.test_groups import PLAN

GEN = '<file role="generator" name="{name}">#include "testlib.h"\nint main(int c, char** v) {{ registerGen(c, v, 1); }}\n</file>'


def router(intent, targets, summary="s"):
    return json.dumps({"intent": intent, "targets": targets, "summary": summary})


async def messages(db, session_id):
    return (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.id))).scalars().all()


# --------------------------------------------------------------------------- apply
async def test_apply_restricts_merges_and_demotes_main(make_ctx, backend, problem):
    problem.statements = {"russian": {"name": "A", "legend": "old legend", "input": "in", "output": "out",
                                      "notes": "note"}}
    problem.solutions["old.cpp"] = {"content": "old\n", "tag": "MA", "mtime": 1}
    ctx = await make_ctx()
    result = await apply_edits(ctx, [
        StatementEdit("russian", "legend", "new legend"),
        FileEdit("solution", "new.cpp", "new\n", "MA"),
        FileEdit("generator", "gen.cpp", "gen\n"),
        LimitsEdit(1234, 4096),
        StandardChecker("std::ncmp.cpp"),
    ], allowed={"statement", "solution", "limits", "checker"}, commit_message="AI: test")

    assert result.dropped == ["gen.cpp"]
    assert "source/gen.cpp" not in problem.files
    st = problem.statements["russian"]
    assert st == {"name": "A", "legend": "new legend", "input": "in", "output": "out", "notes": "note"}
    assert problem.solutions["old.cpp"]["tag"] == "OK"
    assert problem.solutions["new.cpp"]["tag"] == "MA"
    assert problem.info["timeLimit"] == 1200 and problem.info["memoryLimit"] == 1024
    assert problem.checker == "std::ncmp.cpp"
    assert problem.commits == ["AI: test"]
    assert result.needs_build and result.errors == []


async def test_apply_reports_polygon_errors(make_ctx, backend, problem):
    backend.fail_paths[f"/polygon/problems/{problem.id}/validator"] = (400, "compilation error")
    ctx = await make_ctx()
    result = await apply_edits(ctx, [FileEdit("validator", "v.cpp", "x")])
    assert result.errors == ["валидатор v.cpp: compilation error"] and not result.changed


# --------------------------------------------------------------------------- chat
async def test_chat_question_gets_materials(db, make_ctx, llm, backend, problem, session_row):
    backend.put_file(problem, "source", "gen.cpp", "int main() { return 42; }\n")
    llm.on("маршрутизатор", router("question", []))
    llm.on("Отвечай на вопрос пользователя", "Генератор возвращает 42.")
    db.add(Message(session_id=session_row.id, role="user", content="Что делает генератор?"))
    await db.commit()
    msg = (await messages(db, session_row.id))[-1]
    ctx = await make_ctx("chat", {"message_id": msg.id})

    result = await run_chat(ctx)

    assert result == {"intent": "question"}
    reply = (await messages(db, session_row.id))[-1]
    assert reply.role == "assistant" and reply.content == "Генератор возвращает 42."
    assert reply.meta["intent"] == "question"
    for call in llm.calls:
        assert "return 42" in call.user  # every model gets the problem files
    assert llm.calls[0].model == "anthropic/claude-haiku-5.5"
    assert llm.calls[1].model == "anthropic/claude-opus-5.5"


async def test_chat_modify_touches_only_targets(db, make_ctx, llm, backend, problem, session_row):
    problem.statements = {"russian": {"name": "A", "legend": "keep me", "input": "", "output": ""}}
    llm.blocked.add("anthropic/claude-haiku-5.5")
    llm.on("маршрутизатор", router("modify", ["generator"], "fix generator"))
    llm.on("Ты вносишь изменения в задачу", (
        "<reply>Поправил генератор.</reply>" + GEN.format(name="gen.cpp")
        + '<statement lang="russian" field="legend">rewritten</statement>'
    ))
    ctx = await make_ctx("chat", {"text": "Сделай генератор быстрее"})

    result = await run_chat(ctx)

    assert result["build"] is True
    assert "source/gen.cpp" in problem.files
    assert problem.statements["russian"]["legend"] == "keep me"
    modify_call = llm.calls_with("Ты вносишь изменения")[0]
    assert "РАЗРЕШЕНО менять ТОЛЬКО: generator, script" in modify_call.system
    assert [c.model for c in llm.calls_with("маршрутизатор")] == [
        "anthropic/claude-haiku-5.5", "anthropic/claude-sonnet-5.5"]
    reply = (await messages(db, session_row.id))[-1]
    assert "Не применено (вне запроса)" in reply.content and "условие: legend" in reply.content
    assert reply.meta["changed"] == ["gen.cpp"]
    assert problem.commits == ["AI: fix generator"]


async def test_chat_modify_without_auto_build(db, make_ctx, llm, session_row):
    session_row.settings = {"auto_build": False}
    await db.commit()
    llm.on("маршрутизатор", router("modify", ["validator"]))
    llm.on("Ты вносишь изменения в задачу", '<file role="validator" name="v.cpp">int main(){}</file>')
    ctx = await make_ctx("chat", {"text": "x"})
    result = await run_chat(ctx)
    assert result["build"] is False


async def test_chat_build_intent(make_ctx, llm):
    llm.on("маршрутизатор", router("build", []))
    ctx = await make_ctx("chat", {"text": "собери пакет"})
    assert (await run_chat(ctx))["build"] is True


# --------------------------------------------------------------------------- groups
def install_generation_answers(llm):
    llm.on("Обнови валидатор", '<file role="validator" name="validator.cpp">// groups aware\nint main(){}</file>')
    llm.on("Напиши генератор тестов", lambda model, msgs: GEN.format(
        name="x.cpp"))  # the name is forced by the pipeline


async def test_groups_run_sets_up_scoring_as_requested(db, make_ctx, llm, backend, problem, session_row):
    problem.statements = {"russian": {"name": "A", "legend": "L", "input": "I", "output": "O"}}
    for i in (1, 2):
        problem.tests[i] = {"index": i, "manual": True, "input": f"{i}\n", "group": None, "points": None,
                            "useInStatements": True, "scriptLine": None, "description": None}
    install_generation_answers(llm)
    ctx = await make_ctx("groups", {"plan": PLAN})

    result = await run_groups(ctx)

    assert result["build"] is True
    assert {"source/gen_small.cpp", "source/gen_big.cpp", "source/validator.cpp"} <= set(problem.files)
    assert problem.validator == "validator.cpp"
    assert problem.groups_enabled and problem.points_enabled
    tests = problem.tests
    assert [tests[i]["group"] for i in sorted(tests)] == ["0", "0", "1", "1", "1", "1", "2", "2"]
    assert [tests[i]["points"] for i in sorted(tests)] == [0, 0, 0, 0, 0, 30, 0, 70]
    assert problem.groups["1"] == {"pointsPolicy": "COMPLETE_GROUP", "feedbackPolicy": "ICPC", "dependencies": ["0"]}
    assert problem.groups["2"]["dependencies"] == ["0", "1"]
    assert problem.groups["0"]["feedbackPolicy"] == "COMPLETE"
    assert "\\begin{tabular}" in problem.statements["russian"]["scoring"]
    assert problem.statements["russian"]["legend"] == "L"
    assert "AI: test plan applied" in problem.commits
    assert session_row.settings["groups_plan"]["groups"][1]["points"] == 30
    generator_calls = llm.calls_with("Напиши генератор тестов")
    assert len(generator_calls) == 2
    assert any("gen_small 10 random N` x3" in c.user for c in generator_calls)
    reply = (await messages(db, session_row.id))[-1]
    assert "| 1 | 30 | 4 |" in reply.content


async def test_groups_from_request_uses_model_plan(make_ctx, llm, problem):
    plan = {"use_groups": False, "groups": [{"name": "main", "generator": "gen", "cases": [{"args": "5", "count": 2}]}]}
    llm.on("Составь план тестов задачи в JSON", json.dumps(plan))
    install_generation_answers(llm)
    ctx = await make_ctx("groups", {"request": "просто 2 теста"})
    await run_groups(ctx)
    assert not problem.groups_enabled
    assert sorted(t["scriptLine"] for t in problem.tests.values()) == ["gen 5 1", "gen 5 2"]
    assert llm.calls_with("Составь план")[0].json_mode


# --------------------------------------------------------------------------- build
async def test_build_repairs_until_ready(db, make_ctx, llm, backend, problem, session_row):
    backend.build_outcomes = [("FAILED", "Validator rejects test 3"), ("FAILED", "still"), ("READY", "")]
    fixes = iter(["v1", "v2"])
    llm.on("Сборка пакета задачи в Polygon упала",
           lambda m, msgs: f'<reply>fix</reply><file role="validator" name="v.cpp">{next(fixes)}</file>')
    ctx = await make_ctx("build")

    result = await run_build(ctx)

    assert result == {"state": "READY", "package_id": 3, "attempts": 3,
                      "changed": ["валидатор v.cpp: fix", "валидатор v.cpp: fix"]}
    builds = (await db.execute(select(Build).order_by(Build.id))).scalars().all()
    assert [(b.attempt, b.state, b.package_id) for b in builds] == [(1, "FAILED", 1), (2, "FAILED", 2),
                                                                     (3, "READY", 3)]
    repair_calls = llm.calls_with("Сборка пакета задачи в Polygon упала")
    assert "Validator rejects test 3" in repair_calls[0].user
    assert "Предыдущие попытки" in repair_calls[1].user
    contents = [m.content for m in await messages(db, session_row.id)]
    assert contents[-1] == "Пакет #3 собран (после 2 починок)."


async def test_build_gives_up_after_three_repairs(db, make_ctx, llm, backend, session_row):
    backend.build_outcomes = [("FAILED", "boom")] * 4
    llm.on("Сборка пакета задачи в Polygon упала", lambda m, msgs: '<file role="checker" name="c.cpp">x</file>')
    ctx = await make_ctx("build")
    result = await run_build(ctx)
    assert result["needs_user"] and result["attempts"] == 4
    assert len(llm.calls_with("Сборка пакета задачи в Polygon упала")) == 3
    last = (await messages(db, session_row.id))[-1]
    assert last.meta["is_error"] and "после 3 попыток" in last.content and "boom" in last.content


async def test_build_stops_when_model_has_no_fix(make_ctx, llm, backend):
    backend.build_outcomes = [("FAILED", "boom")]
    llm.on("Сборка пакета задачи в Polygon упала", "<reply>не знаю</reply>")
    result = await run_build(await make_ctx("build"))
    assert result["needs_user"] and result["attempts"] == 1


# --------------------------------------------------------------------------- generate
async def test_generate_whole_problem(db, make_ctx, llm, backend, problem, session_row):
    llm.on("составь полное условие задачи", (
        '<statement lang="russian" field="name">Сумма</statement>'
        '<statement lang="russian" field="legend">Даны $a$ и $b$.</statement>'
        '<statement lang="russian" field="input">Два числа.</statement>'
        '<statement lang="russian" field="output">Сумма.</statement>'
        '<limits time_limit="2000" memory_limit="256"/><tags>math</tags>'
        "<sample>1 2</sample><sample>3 4</sample><reply>Простая задача.</reply>"
    ))
    llm.on("авторское (главное) решение", '<file role="solution" name="x.cpp">main</file>')
    llm.on("переборное решение", '<file role="solution" name="y.cpp">brute</file>')
    install_generation_answers(llm)
    llm.on("Напиши валидатор входных данных", '<file role="validator" name="q.cpp">validator</file>')
    llm.on("Выбери чекер", '<checker standard="std::ncmp.cpp"/><reply>одно число</reply>')
    ctx = await make_ctx("generate", {"idea": "сложить два числа", "plan": PLAN})

    result = await run_generate(ctx)

    assert result["build"] is True, result
    assert problem.statements["russian"]["name"] == "Сумма"
    assert problem.info["timeLimit"] == 2000 and problem.tags == ["math"]
    assert problem.solutions["main.cpp"]["tag"] == "MA" and problem.solutions["brute.cpp"]["tag"] == "TO"
    assert problem.checker == "std::ncmp.cpp"
    assert problem.files["source/validator.cpp"]["content"].startswith("// groups aware")
    samples = [t for t in problem.tests.values() if t["useInStatements"]]
    assert [t["index"] for t in samples] == [1, 2] and all(t["group"] == "0" for t in samples)
    assert sum(t["points"] or 0 for t in problem.tests.values()) == 100
    reply = (await messages(db, session_row.id))[-1]
    assert reply.meta["intent"] == "generate" and "Задача сгенерирована" in reply.content
    assert ctx.run.progress_total >= ctx.run.progress_done


async def test_generate_refuses_interactive(db, make_ctx, session_row):
    import pytest

    from authoring.pipeline.context import PipelineError
    session_row.problem_type = "interactive"
    await db.commit()
    with pytest.raises(PipelineError, match="только обычные"):
        await run_generate(await make_ctx("generate", {"idea": "x"}))


# --------------------------------------------------------------------------- review fixes
async def test_statement_edit_aborts_when_current_statement_unreadable(make_ctx, backend, problem):
    problem.statements = {"russian": {"name": "A", "legend": "keep", "input": "i", "output": "o"}}
    ctx = await make_ctx()
    await ctx.snapshot(refresh=True)
    backend.fail_paths[f"/polygon/problems/{problem.id}/statement"] = (500, "boom")
    result = await apply_edits(ctx, [StatementEdit("russian", "scoring", "table")])
    assert not result.changed and "не удалось прочитать" in result.errors[0]
    assert problem.statements["russian"]["legend"] == "keep"


async def test_too_big_files_are_not_rewritten(make_ctx, backend, problem):
    from authoring.sync.dossier import MAX_FILE_CHARS
    backend.put_file(problem, "source", "big.cpp", "x" * (MAX_FILE_CHARS + 10))
    ctx = await make_ctx()
    result = await apply_edits(ctx, [FileEdit("generator", "big.cpp", "short\n")])
    assert "слишком большой" in result.errors[0]
    assert len(problem.files["source/big.cpp"]["content"]) > MAX_FILE_CHARS


async def test_generate_intent_on_filled_problem_is_not_regenerated(db, make_ctx, llm, backend, problem, session_row):
    problem.statements = {"russian": {"name": "A", "legend": "есть условие", "input": "", "output": ""}}
    llm.on("маршрутизатор", router("generate", []))
    llm.on("Отвечай на вопрос пользователя", "Ответ.")
    ctx = await make_ctx("chat", {"text": "сгенерируй тесты"})
    result = await run_chat(ctx)
    assert result == {"intent": "question"}
    assert not llm.calls_with("составь полное условие")
    assert "целиком я её не пересоздаю" in (await messages(db, session_row.id))[-1].content


async def test_generator_edit_keeps_script_when_plan_exists(db, make_ctx, llm, session_row):
    session_row.settings = {"auto_build": True, "groups_plan": {"use_groups": True, "groups": []}}
    await db.commit()
    llm.on("маршрутизатор", router("modify", ["generator"]))
    llm.on("Ты вносишь изменения в задачу", GEN.format(name="gen.cpp") + "<script>gen 1 > $</script>")
    ctx = await make_ctx("chat", {"text": "поправь генератор"})
    await run_chat(ctx)
    assert "РАЗРЕШЕНО менять ТОЛЬКО: generator." in llm.calls_with("Ты вносишь")[0].system
    assert "скрипт тестов" in (await messages(db, session_row.id))[-1].meta["dropped"]


async def test_cancelled_build_is_not_left_running(db, make_ctx, backend):
    from authoring.pipeline.context import RunCancelled
    ctx = await make_ctx("build")
    ctx.run.cancel_requested = True
    await db.commit()
    backend.build_outcomes = [("READY", "")]
    import pytest
    with pytest.raises(RunCancelled):
        await run_build(ctx)
    build = (await db.execute(select(Build))).scalars().one()
    assert build.state == "CANCELLED"


async def test_build_timeout_stops_without_repair(make_ctx, llm, backend, monkeypatch):
    from authoring.settings import settings
    monkeypatch.setattr(settings, "BUILD_TIMEOUT_SECONDS", 0)
    result = await run_build(await make_ctx("build"))
    assert result["state"] == "TIMEOUT" and result["needs_user"]
    assert llm.calls == []
