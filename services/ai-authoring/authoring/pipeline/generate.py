"""Whole-problem generation and the groups run.

``generate`` (a problem from an idea):
statement + limits + samples -> main solution -> validator -> checker ->
test plan (the user's or the model's) -> generators/script/groups/scoring ->
a brute-force ``TO`` solution for cross-checking -> (the runner chains a build).

The problem type changes some steps:

* interactive: the statement gets the interaction protocol, the main solution
  talks to the interactor, an interactor step is added, the checker compares
  the interactor's output (``tout``); tests are the interactor's hidden data;
* output-only: the main solution is the jury solver (its output is the jury
  answer), the checker is a scorer with ``quitp``, no groups, every test is
  worth ``OUTPUT_ONLY_TEST_POINTS``; the statement gets the scoring section.

Neither gets a brute-force solution: a slow interactive strategy fails on the
query limit (WA, not TL), and an output-only problem has no time to exceed.
"""
from __future__ import annotations

import logging

from authoring.llm import prompts
from authoring.llm.client import LLMError, Msg, parse_json
from authoring.llm.problem_types import INTERACTIVE, OUTPUT_ONLY, OUTPUT_ONLY_TEST_POINTS, REGULAR, normalize_type
from authoring.llm.protocol import (
    FileEdit,
    Parsed,
    SampleEdit,
    StandardChecker,
    StatementEdit,
    parse,
    single_file,
)
from authoring.pipeline.apply import ApplyResult, apply_edits
from authoring.pipeline.context import PipelineError, RunContext, plural
from authoring.pipeline.groups import PlanError, TestPlan, normalize_plan
from authoring.pipeline.plan_apply import apply_plan
from authoring.polygon.client import PolygonError

logger = logging.getLogger(__name__)

STATEMENT_ATTEMPTS = 2
OUTPUT_ONLY_NO_GROUPS = (
    "в output-only задаче групп нет: баллы начисляет скорер за каждый тест "
    f"(до {OUTPUT_ONLY_TEST_POINTS} за тест)"
)

# statement sections a problem of the type must have (besides legend/input/output)
REQUIRED_SECTIONS = {INTERACTIVE: ("interaction", "«Протокол взаимодействия»"),
                     OUTPUT_ONLY: ("scoring", "«Система оценки»")}


def problem_kind(ctx: RunContext) -> str:
    return normalize_type(ctx.session.problem_type)


async def _ask_file(ctx: RunContext, system: str, *, role: str, name: str, tag: str | None = None,
                    task: str = "") -> FileEdit:
    dossier = await ctx.dossier()
    completion = await ctx.llm.complete(ctx.model, prompts.file_messages(system, dossier, task))
    if completion.truncated:
        raise PipelineError(f"{name}: ответ модели обрезан по лимиту токенов")
    edit = single_file(completion.text, role=role)
    edit.role, edit.name = role, name
    if tag:
        edit.tag = tag
    return edit


def check_plan_type(ctx: RunContext, plan: TestPlan) -> TestPlan:
    if plan.use_groups and problem_kind(ctx) == OUTPUT_ONLY:
        raise PlanError(OUTPUT_ONLY_NO_GROUPS)
    return plan


async def make_plan(ctx: RunContext, request: str) -> TestPlan:
    """Ask the model for a test plan (JSON) and validate it, with one retry on errors."""
    dossier = await ctx.dossier()
    messages = prompts.plan_messages(dossier, request, problem_kind(ctx))
    error = ""
    for _ in range(2):
        if error:
            messages = messages + [Msg.text("user", f"План отклонён: {error}. Исправь и верни JSON заново.")]
        completion = await ctx.llm.complete(ctx.model, messages, json_mode=True)
        try:
            return check_plan_type(ctx, normalize_plan(parse_json(completion.text)))
        except (PlanError, LLMError) as e:
            error = str(e)
    raise PipelineError(f"модель не смогла составить корректный план тестов: {error}")


def _given_plan(ctx: RunContext, raw: dict) -> TestPlan:
    try:
        return check_plan_type(ctx, normalize_plan(raw))
    except PlanError as e:
        raise PipelineError(f"план групп: {e}")


async def _save_samples(ctx: RunContext, samples: list[SampleEdit]) -> ApplyResult:
    """Fresh problem: samples become manual tests 1..k shown in the statement."""
    result = ApplyResult()
    for index, sample in enumerate(samples, start=1):
        try:
            await ctx.client.save_test(
                ctx.session.polygon_id, index, test_input=sample.input, test_use_in_statements=True,
                check_existing=False,
            )
            result.changed.append(f"пример {index}")
            result.targets.add("samples")
        except PolygonError as e:
            result.errors.append(f"пример {index}: {e.message}")
    ctx.invalidate()
    return result


def _has_legend(parsed: Parsed) -> bool:
    return any(isinstance(e, StatementEdit) and e.field == "legend" and e.content.strip() for e in parsed.edits)


async def _ask_statement(ctx: RunContext, idea: str, extra: str) -> Parsed | None:
    """Statement, limits and samples; one corrective retry when the legend is missing.

    Returns the parsed answer with a legend, or the last answer without one (its
    ``edits`` emptied) so the caller can show the model's own words, or None.
    """
    messages = prompts.statement_messages(idea, ctx.session.problem_type, extra)
    last: Parsed | None = None
    for attempt in range(1, STATEMENT_ATTEMPTS + 1):
        completion = await ctx.llm.complete(ctx.model, messages)
        parsed = parse(completion.text)
        if _has_legend(parsed) and not completion.truncated:
            return parsed
        reason = "ответ обрезан по лимиту токенов" if completion.truncated else "нет блока legend"
        logger.warning(
            "run %s: statement attempt %d without a legend (%s, model %s, %d chars, warnings %s): %.2000s",
            ctx.run_id, attempt, reason, completion.model, len(completion.text), parsed.warnings, completion.text,
        )
        last = Parsed(reply=parsed.reply, warnings=parsed.warnings)
        messages = messages + [
            Msg.text("assistant", completion.text or "(пустой ответ)"),
            Msg.text("user", prompts.STATEMENT_RETRY),
        ]
    return last


async def _statement_missing(ctx: RunContext, parsed: Parsed | None) -> dict:
    """The model kept answering without a statement: show what it said instead of a bare error."""
    said = (parsed.reply if parsed else "").strip()
    if not said:
        raise PipelineError("модель не вернула условие (две попытки); попробуйте ещё раз или другую модель")
    text = (
        "Не удалось получить условие задачи: модель ответила без него. Её ответ:\n\n"
        f"{said[:4000]}\n\n"
        "Уточните идею (например, ответьте на вопросы выше) и отправьте её снова."
    )
    await ctx.say(text, intent="generate", errors=["модель не вернула условие"])
    return {"needs_user": True, "changed": [], "errors": ["модель не вернула условие"]}


async def _checker_step(ctx: RunContext, kind: str) -> ApplyResult:
    """Checker by type: scorer (output-only), tout comparison (interactive), standard or own (regular)."""
    if kind == OUTPUT_ONLY:
        scorer = await _ask_file(ctx, prompts.SCORER_SYSTEM, role="checker", name="scorer.cpp")
        return await apply_edits(ctx, [scorer], allowed={"checker"})
    system = prompts.INTERACTIVE_CHECKER_SYSTEM if kind == INTERACTIVE else prompts.CHECKER_SYSTEM
    dossier = await ctx.dossier()
    completion = await ctx.llm.complete(ctx.model, prompts.file_messages(system, dossier))
    checker = [e for e in parse(completion.text).edits if isinstance(e, (StandardChecker, FileEdit))]
    if not checker:
        checker = [StandardChecker("std::wcmp.cpp")]
    edit = checker[0]
    if isinstance(edit, FileEdit):
        edit.role, edit.name = "checker", edit.name or "checker.cpp"
    return await apply_edits(ctx, [edit], allowed={"checker"})


async def run_generate(ctx: RunContext) -> dict:
    kind = problem_kind(ctx)
    payload = ctx.run.payload or {}
    idea = (payload.get("idea") or "").strip()
    if not idea:
        raise PipelineError("Опишите идею задачи")
    raw_plan = payload.get("plan")
    want_groups = bool(payload.get("groups", raw_plan is not None)) and kind != OUTPUT_ONLY
    with_brute = bool(payload.get("brute", True)) and kind == REGULAR
    given_plan = _given_plan(ctx, raw_plan) if raw_plan is not None else None
    with_interactor = kind == INTERACTIVE

    def steps_total(groups: bool) -> int:
        return 6 + int(with_interactor) + (4 if groups else 2) + int(with_brute)

    total = steps_total(want_groups)
    result = ApplyResult()
    n = 0

    async def step(text: str) -> None:
        nonlocal n
        await ctx.step(text, done=n, total=total)
        n += 1

    await step("Читаю задачу")
    await ctx.snapshot(refresh=True, announce=True)

    await step("Условие, ограничения и примеры")
    parsed = await _ask_statement(ctx, idea, payload.get("extra") or "")
    if parsed is None or not parsed.edits:
        return await _statement_missing(ctx, parsed)
    samples = [e for e in parsed.edits if isinstance(e, SampleEdit)]
    other = [e for e in parsed.edits if not isinstance(e, SampleEdit)]
    if kind in REQUIRED_SECTIONS:
        field, label = REQUIRED_SECTIONS[kind]
        if not any(isinstance(e, StatementEdit) and e.field == field and e.content.strip() for e in other):
            result.errors.append(f"в условии нет раздела {label}: допишите его или попросите ИИ в чате")
    result.merge(await apply_edits(ctx, other, allowed={"statement", "limits", "tags"}))
    summary = parsed.reply

    await step("Эталонное решение жюри" if kind == OUTPUT_ONLY else "Авторское решение")
    # the idea may fix the intended complexity/approach ("solution must be linear"):
    # the statement alone loses it, so the author's solution gets it explicitly
    intent = f"Идея автора задачи:\n{idea}" + (f"\n\nЗамысел решения:\n{summary}" if summary else "")
    main = await _ask_file(
        ctx, prompts.main_solution_system(kind), role="solution", name="main.cpp", tag="MA",
        task=intent + "\n\nНапиши авторское решение по материалам, соблюдая асимптотику и подход из замысла.",
    )
    result.merge(await apply_edits(ctx, [main], allowed={"solution"}))

    await step("Примеры в условии")
    result.merge(await _save_samples(ctx, samples))

    await step("Валидатор")
    validator = await _ask_file(ctx, prompts.VALIDATOR_SYSTEM, role="validator", name="validator.cpp")
    result.merge(await apply_edits(ctx, [validator], allowed={"validator"}))

    if with_interactor:
        await step("Интерактор")
        interactor = await _ask_file(ctx, prompts.INTERACTOR_SYSTEM, role="interactor", name="interactor.cpp")
        result.merge(await apply_edits(ctx, [interactor], allowed={"interactor"}))

    await step("Скорер (чекер с баллами)" if kind == OUTPUT_ONLY else "Чекер")
    result.merge(await _checker_step(ctx, kind))

    await step("План тестов")
    if given_plan is not None:
        plan = given_plan
    else:
        request = idea + (
            "\n\nНужны группы тестов (подзадачи) с баллами, сумма 100." if want_groups
            else "\n\nГруппы тестов не нужны (use_groups=false)."
        )
        plan = await make_plan(ctx, request)
    total = steps_total(plan.use_groups)
    result.merge(await apply_plan(ctx, plan, step_offset=n - 1, total=total))

    if with_brute:
        await ctx.step("Переборное решение для проверки", done=total - 1, total=total)
        try:
            brute = await _ask_file(ctx, prompts.BRUTE_SYSTEM, role="solution", name="brute.cpp", tag="TO")
            result.merge(await apply_edits(ctx, [brute], allowed={"solution"}))
        except (LLMError, PipelineError) as e:
            result.errors.append(f"brute.cpp: {e}")

    try:
        await ctx.client.commit(ctx.session.polygon_id, "AI: problem generated")
    except PolygonError as e:
        result.errors.append(f"commit: {e.message}")

    text = "### Задача сгенерирована\n\n" + (summary + "\n\n" if summary else "")
    tests = plural(sum(g.test_count for g in plan.groups), "тест", "теста", "тестов")
    if plan.use_groups:
        text += f"План тестов: {plural(len(plan.groups), 'группа', 'группы', 'групп')}, {tests} из скрипта"
        text += f", сумма баллов {plan.total_points:g}"
    elif kind == OUTPUT_ONLY:
        text += f"Тесты: {tests} из скрипта, до {OUTPUT_ONLY_TEST_POINTS} баллов за каждый (скорер)"
    else:
        text += f"План тестов: без групп, {tests} из скрипта"
    text += ".\n\n" + result.report()
    if ctx.auto_build:
        text += "\n\nЗапускаю сборку пакета с проверкой."
    await ctx.say(text, intent="generate", changed=result.changed, errors=result.errors)
    return {"build": True, "changed": result.changed, "errors": result.errors}


async def run_groups(ctx: RunContext) -> dict:
    """Apply a plan given by the user (editor) or derived from their request."""
    payload = ctx.run.payload or {}
    await ctx.step("Читаю задачу", done=0, total=5)
    await ctx.snapshot(refresh=True, announce=True)

    if payload.get("plan") is not None:
        plan = _given_plan(ctx, payload["plan"])
    else:
        request = (payload.get("request") or "").strip()
        if not request:
            raise PipelineError("Опишите группы и баллы или заполните план")
        await ctx.step("Составляю план групп", done=1, total=5)
        plan = await make_plan(ctx, request)

    result = await apply_plan(ctx, plan, step_offset=1, total=5)
    lines = [
        "### План тестов применён",
        "",
        "| Группа | Баллы | Тестов | Ограничения | Зависит от |",
        "|---|---|---|---|---|",
    ]
    for g in plan.groups:
        count = "примеры" if g.samples else str(g.test_count)
        deps = ", ".join(g.dependencies) or "—"
        lines.append(f"| {g.name} | {g.points:g} | {count} | {g.description or '—'} | {deps} |")
    lines.append("")
    if plan.use_groups:
        lines.append("Каждая группа: COMPLETE_GROUP + first-failed (ICPC), все баллы группы — на одном тесте.")
    elif problem_kind(ctx) == OUTPUT_ONLY:
        lines.append(f"Групп нет: каждый тест стоит до {OUTPUT_ONLY_TEST_POINTS} баллов, их начисляет скорер.")
    else:
        lines.append("Групп нет.")
    lines.append("")
    lines.append(result.report())
    if ctx.auto_build:
        lines.append("\nЗапускаю сборку пакета.")
    await ctx.say("\n".join(lines), intent="groups", changed=result.changed, errors=result.errors,
                  plan=plan.to_dict())
    return {"build": True, "changed": result.changed, "errors": result.errors}
