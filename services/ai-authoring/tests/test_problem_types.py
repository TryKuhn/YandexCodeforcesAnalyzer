"""Interactive and output-only problems, and solutions with a requested verdict."""
import json

import pytest
from sqlalchemy import select

from authoring.llm.problem_types import OUTPUT_ONLY_TEST_POINTS
from authoring.models import Message
from authoring.pipeline.chat import run_chat
from authoring.pipeline.context import PipelineError
from authoring.pipeline.generate import run_generate, run_groups
from authoring.sync.service import sync_session
from tests.test_groups import PLAN
from tests.test_pipeline import GEN, install_generation_answers, router

NO_GROUPS = {"use_groups": False, "groups": [
    {"name": "main", "generator": "gen", "cases": [{"args": "5", "count": 2}, {"args": "100", "count": 1}]}]}


async def messages(db, session_id):
    rows = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.id))
    return rows.scalars().all()


async def set_type(db, session_row, problem_type, problem=None):
    session_row.problem_type = problem_type
    await db.commit()
    if problem is not None:  # as the type switch does: Polygon's flag follows the type
        problem.info["interactive"] = problem_type == "interactive"


def common_answers(llm, statement):
    llm.on("составь полное условие задачи", statement)
    llm.on("Напиши валидатор входных данных", '<file role="validator" name="v.cpp">validator</file>')
    llm.on("переборное решение", '<file role="solution" name="b.cpp">brute</file>')
    install_generation_answers(llm)


# --------------------------------------------------------------------------- interactive
INTERACTIVE_STATEMENT = (
    '<statement lang="russian" field="name">Угадай число</statement>'
    '<statement lang="russian" field="legend">Жюри загадало $x$.</statement>'
    '<statement lang="russian" field="input">Ничего.</statement>'
    '<statement lang="russian" field="output">Ответ \\texttt{! x}.</statement>'
    '<statement lang="russian" field="interaction">Запрос \\texttt{? y}, ответ $<$, $>$ или $=$.</statement>'
    "<sample>5</sample><reply>Бинпоиск.</reply>"
)


async def test_generate_interactive_problem(db, make_ctx, llm, backend, problem, session_row):
    await set_type(db, session_row, "interactive", problem)
    common_answers(llm, INTERACTIVE_STATEMENT)
    llm.on("авторское (главное) решение", '<file role="solution" name="x.cpp">main with flush</file>')
    llm.on("Напиши интерактор", '<file role="interactor" name="i.cpp">registerInteraction</file>')
    llm.on("Выбери чекер для ИНТЕРАКТИВНОЙ", '<checker standard="std::wcmp.cpp"/>')
    ctx = await make_ctx("generate", {"idea": "угадай число за 30 запросов", "plan": NO_GROUPS})

    result = await run_generate(ctx)

    assert result["build"] is True, result
    assert problem.interactor == "interactor.cpp"
    assert problem.files["source/interactor.cpp"]["content"].startswith("registerInteraction")
    assert problem.checker == "std::wcmp.cpp"
    assert problem.statements["russian"]["interaction"].startswith("Запрос")
    assert problem.solutions["main.cpp"]["tag"] == "MA"
    # no brute force for an interactive problem: a slow strategy is WA (query limit), not TL
    assert not llm.calls_with("переборное решение") and "brute.cpp" not in problem.solutions
    statement_call = llm.calls_with("составь полное условие задачи")[0]
    assert 'field="interaction"' in statement_call.system
    main_call = llm.calls_with("авторское (главное) решение")[0]
    assert "ИНТЕРАКТИВНОЙ" in main_call.system and "flush" in main_call.system
    # every call with materials knows the type
    assert "ТИП ЗАДАЧИ: ИНТЕРАКТИВНАЯ" in llm.calls_with("Напиши интерактор")[0].user
    assert ctx.run.progress_total >= ctx.run.progress_done
    assert sum(1 for t in problem.tests.values() if not t["manual"]) == 3


async def test_interactive_without_interaction_section_is_reported(db, make_ctx, llm, problem, session_row):
    await set_type(db, session_row, "interactive", problem)
    common_answers(llm, INTERACTIVE_STATEMENT.replace("field=\"interaction\"", "field=\"notes\""))
    llm.on("авторское (главное) решение", '<file role="solution" name="x.cpp">main</file>')
    llm.on("Напиши интерактор", '<file role="interactor" name="i.cpp">interactor</file>')
    llm.on("Выбери чекер", '<checker standard="std::wcmp.cpp"/>')

    result = await run_generate(await make_ctx("generate", {"idea": "угадай", "plan": NO_GROUPS}))

    assert any("Протокол взаимодействия" in e for e in result["errors"])


# --------------------------------------------------------------------------- output-only
OUTPUT_ONLY_STATEMENT = (
    '<statement lang="russian" field="name">Покраска</statement>'
    '<statement lang="russian" field="legend">Раскрасьте граф.</statement>'
    '<statement lang="russian" field="input">Граф.</statement>'
    '<statement lang="russian" field="output">Цвета.</statement>'
    '<statement lang="russian" field="scoring">До 10 баллов за тест.</statement>'
    "<sample>3 2</sample><reply>Эвристика.</reply>"
)


async def test_generate_output_only_problem(db, make_ctx, llm, backend, problem, session_row):
    await set_type(db, session_row, "output_only")
    common_answers(llm, OUTPUT_ONLY_STATEMENT)
    llm.on("Напиши эталонный решатель жюри", '<file role="solution" name="x.cpp">jury</file>')
    llm.on("Напиши чекер-скорер", '<file role="checker" name="s.cpp">quitp</file>')
    llm.on("Составь план тестов", json.dumps(NO_GROUPS))
    ctx = await make_ctx("generate", {"idea": "раскраска графа в минимум цветов", "groups": True})

    result = await run_generate(ctx)

    assert result["build"] is True, result
    assert problem.solutions["main.cpp"] == {**problem.solutions["main.cpp"], "content": "jury\n", "tag": "MA"}
    assert problem.checker == "scorer.cpp" and problem.files["source/scorer.cpp"]["content"] == "quitp\n"
    assert problem.statements["russian"]["scoring"].startswith("До 10")
    assert problem.points_enabled and not problem.groups_enabled
    # every test, the sample too, is worth the same maximum
    assert {t["points"] for t in problem.tests.values()} == {OUTPUT_ONLY_TEST_POINTS}
    assert len(problem.tests) == 4
    assert not llm.calls_with("переборное решение")
    # groups were asked for, but an output-only problem has none
    assert "Группы тестов не нужны" in llm.calls_with("Составь план тестов")[0].user
    reply = (await messages(db, session_row.id))[-1]
    assert f"до {OUTPUT_ONLY_TEST_POINTS} баллов за каждый" in reply.content
    assert ctx.run.progress_total >= ctx.run.progress_done


async def test_output_only_refuses_groups(db, make_ctx, llm, problem, session_row):
    await set_type(db, session_row, "output_only")
    with pytest.raises(PipelineError, match="групп нет"):
        await run_groups(await make_ctx("groups", {"plan": PLAN}))


async def test_output_only_model_plan_with_groups_is_retried(db, make_ctx, llm, problem, session_row):
    await set_type(db, session_row, "output_only")
    answers = iter([json.dumps(PLAN), json.dumps(NO_GROUPS)])
    llm.on("Составь план тестов", lambda model, msgs: next(answers))
    install_generation_answers(llm)

    await run_groups(await make_ctx("groups", {"request": "тесты разного размера"}))

    retry = llm.calls_with("Составь план тестов")[1]
    assert "групп нет" in retry.user
    assert problem.points_enabled and all(t["points"] == OUTPUT_ONLY_TEST_POINTS for t in problem.tests.values())


# --------------------------------------------------------------------------- type in every request
async def test_type_guide_reaches_router_and_answers(db, make_ctx, llm, problem, session_row):
    await set_type(db, session_row, "output_only")
    llm.on("маршрутизатор", router("question", []))
    llm.on("Отвечай на вопрос пользователя", "Ответ.")
    await run_chat(await make_ctx("chat", {"text": "как считаются баллы?"}))
    assert "ТИП ЗАДАЧИ: OUTPUT-ONLY" in llm.calls_with("маршрутизатор")[0].user
    assert "ТИП ЗАДАЧИ: OUTPUT-ONLY" in llm.calls_with("Отвечай на вопрос пользователя")[0].user


async def test_sync_follows_polygon_interactive_flag(db, session_row, problem, client_factory):
    problem.info["interactive"] = True
    await sync_session(db, session_row, client_factory(session_row.user_id), announce=False)
    assert session_row.problem_type == "interactive"
    problem.info["interactive"] = False
    await sync_session(db, session_row, client_factory(session_row.user_id), announce=False)
    assert session_row.problem_type == "regular"
    # output-only has no flag in Polygon: it is kept
    session_row.problem_type = "output_only"
    await sync_session(db, session_row, client_factory(session_row.user_id), announce=False)
    assert session_row.problem_type == "output_only"


async def test_create_output_only_problem_enables_points(api, backend):
    data = (await api.post("/api/ai/problems", json={"name": "oo", "problem_type": "output_only"})).json()
    created = backend.problems[data["polygon_id"]]
    assert created.points_enabled and data["session"]["problem_type"] == "output_only"


# --------------------------------------------------------------------------- verdict solutions
async def test_chat_adds_solution_with_requested_verdict(db, make_ctx, llm, problem, session_row):
    problem.solutions["main.cpp"] = {"content": "main", "tag": "MA", "mtime": 1}
    llm.on("маршрутизатор", router("modify", ["solution"]))
    llm.on("Ты вносишь изменения в задачу",
           '<reply>O(n^2) при n = 1e5 не успеет.</reply><file role="solution" name="tl_n2.cpp" tag="TL">slow</file>')

    result = await run_chat(await make_ctx("chat", {"text": "сгенерируй решение за n^2, которое не проходит по времени"}))

    assert problem.solutions["tl_n2.cpp"]["tag"] == "TL"
    assert problem.solutions["main.cpp"]["tag"] == "MA" and problem.solutions["main.cpp"]["content"] == "main"
    assert result["build"] is True
    system = llm.calls_with("Ты вносишь изменения в задачу")[0].system
    assert "TL -- ОБЯЗАНО превысить" in system and "создай НОВЫЙ файл решения" in system
    assert "TO -- правильное ИЛИ превышает время" in system


async def test_main_solution_is_never_turned_into_a_failing_one(db, make_ctx, llm, problem, session_row):
    problem.solutions["main.cpp"] = {"content": "main", "tag": "MA", "mtime": 1}
    llm.on("маршрутизатор", router("modify", ["solution"]))
    llm.on("Ты вносишь изменения в задачу", '<file role="solution" name="main.cpp" tag="ML">huge table</file>')

    await run_chat(await make_ctx("chat", {"text": "добавь решение, которое превышает память"}))

    assert problem.solutions["main.cpp"] == {**problem.solutions["main.cpp"], "content": "main", "tag": "MA"}
    assert problem.solutions["main_ml.cpp"]["tag"] == "ML"
    reply = (await messages(db, session_row.id))[-1]
    assert "main_ml.cpp" in reply.content


async def test_solution_request_without_router_targets(db, make_ctx, llm, problem, session_row):
    llm.on("маршрутизатор", router("modify", []))
    llm.on("Ты вносишь изменения в задачу", '<file role="solution" name="wa.cpp" tag="WA">wrong</file>')
    await run_chat(await make_ctx("chat", {"text": "напиши неверное решение с переполнением int"}))
    assert problem.solutions["wa.cpp"]["tag"] == "WA"
    assert "РАЗРЕШЕНО менять ТОЛЬКО: solution." in llm.calls_with("Ты вносишь")[0].system


async def test_generator_for_interactive_tests_knows_hidden_data(db, make_ctx, llm, problem, session_row):
    await set_type(db, session_row, "interactive", problem)
    llm.on("Составь план тестов", json.dumps(NO_GROUPS))
    llm.on("Напиши генератор тестов", GEN.format(name="g.cpp"))
    await run_groups(await make_ctx("groups", {"request": "10 тестов"}))
    plan_call = llm.calls_with("Составь план тестов")[0]
    assert "СКРЫТЫЕ данные для интерактора" in plan_call.system
