"""Whole-problem generation and the groups run.

``generate`` (a regular problem from an idea):
statement + limits + samples -> main solution -> validator -> checker ->
test plan (the user's or the model's) -> generators/script/groups/scoring ->
a brute-force ``TO`` solution for cross-checking -> (the runner chains a build).
"""
from __future__ import annotations

import logging

from authoring.llm import prompts
from authoring.llm.client import LLMError, Msg, parse_json
from authoring.llm.protocol import FileEdit, SampleEdit, StandardChecker, parse, single_file
from authoring.models import ProblemType
from authoring.pipeline.apply import ApplyResult, apply_edits
from authoring.pipeline.context import PipelineError, RunContext
from authoring.pipeline.groups import PlanError, TestPlan, normalize_plan
from authoring.pipeline.plan_apply import apply_plan
from authoring.polygon.client import PolygonError

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = (ProblemType.REGULAR.value,)


def _require_supported(ctx: RunContext) -> None:
    if ctx.session.problem_type not in SUPPORTED_TYPES:
        raise PipelineError(
            "Автоматическая генерация пока поддерживает только обычные задачи; "
            "для интерактивных и output-only доступны вопросы и точечные правки в чате."
        )


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


async def make_plan(ctx: RunContext, request: str) -> TestPlan:
    """Ask the model for a test plan (JSON) and validate it, with one retry on errors."""
    dossier = await ctx.dossier()
    messages = prompts.plan_messages(dossier, request)
    error = ""
    for _ in range(2):
        if error:
            messages = messages + [Msg.text("user", f"План отклонён: {error}. Исправь и верни JSON заново.")]
        completion = await ctx.llm.complete(ctx.model, messages, json_mode=True)
        try:
            return normalize_plan(parse_json(completion.text))
        except (PlanError, LLMError) as e:
            error = str(e)
    raise PipelineError(f"модель не смогла составить корректный план тестов: {error}")


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


async def run_generate(ctx: RunContext) -> dict:
    _require_supported(ctx)
    payload = ctx.run.payload or {}
    idea = (payload.get("idea") or "").strip()
    if not idea:
        raise PipelineError("Опишите идею задачи")
    raw_plan = payload.get("plan")
    want_groups = bool(payload.get("groups", raw_plan is not None))
    with_brute = bool(payload.get("brute", True))
    def steps_total(groups: bool) -> int:
        return 6 + (4 if groups else 2) + (1 if with_brute else 0)

    total = steps_total(want_groups)
    result = ApplyResult()

    await ctx.step("Читаю задачу", done=0, total=total)
    await ctx.snapshot(refresh=True, announce=True)

    await ctx.step("Условие, ограничения и примеры", done=1, total=total)
    completion = await ctx.llm.complete(
        ctx.model, prompts.statement_messages(idea, ctx.session.problem_type, payload.get("extra") or "")
    )
    parsed = parse(completion.text)
    samples = [e for e in parsed.edits if isinstance(e, SampleEdit)]
    other = [e for e in parsed.edits if not isinstance(e, SampleEdit)]
    if not any(getattr(e, "field", None) == "legend" for e in other):
        raise PipelineError("модель не вернула условие")
    result.merge(await apply_edits(ctx, other, allowed={"statement", "limits", "tags"}))
    summary = parsed.reply

    await ctx.step("Авторское решение", done=2, total=total)
    main = await _ask_file(ctx, prompts.MAIN_SOLUTION_SYSTEM, role="solution", name="main.cpp", tag="MA")
    result.merge(await apply_edits(ctx, [main], allowed={"solution"}))

    await ctx.step("Примеры в условии", done=3, total=total)
    result.merge(await _save_samples(ctx, samples))

    await ctx.step("Валидатор", done=4, total=total)
    validator = await _ask_file(ctx, prompts.VALIDATOR_SYSTEM, role="validator", name="validator.cpp")
    result.merge(await apply_edits(ctx, [validator], allowed={"validator"}))

    await ctx.step("Чекер", done=5, total=total)
    dossier = await ctx.dossier()
    completion = await ctx.llm.complete(ctx.model, prompts.file_messages(prompts.CHECKER_SYSTEM, dossier))
    checker = [e for e in parse(completion.text).edits if isinstance(e, (StandardChecker, FileEdit))]
    if not checker:
        checker = [StandardChecker("std::wcmp.cpp")]
    for edit in checker[:1]:
        if isinstance(edit, FileEdit):
            edit.role, edit.name = "checker", edit.name or "checker.cpp"
    result.merge(await apply_edits(ctx, checker[:1], allowed={"checker"}))

    await ctx.step("План тестов", done=6, total=total)
    if raw_plan is not None:
        try:
            plan = normalize_plan(raw_plan)
        except PlanError as e:
            raise PipelineError(f"план групп: {e}")
    else:
        request = idea + (
            "\n\nНужны группы тестов (подзадачи) с баллами, сумма 100." if want_groups
            else "\n\nГруппы тестов не нужны (use_groups=false)."
        )
        plan = await make_plan(ctx, request)
    total = steps_total(plan.use_groups)
    result.merge(await apply_plan(ctx, plan, step_offset=6, total=total))

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
    text += f"План тестов: {len(plan.groups)} групп(ы), {sum(g.test_count for g in plan.groups)} тестов из скрипта"
    if plan.use_groups:
        text += f", сумма баллов {plan.total_points:g}"
    text += ".\n\n" + result.report()
    if ctx.auto_build:
        text += "\n\nЗапускаю сборку пакета с проверкой."
    await ctx.say(text, intent="generate", changed=result.changed, errors=result.errors)
    return {"build": True, "changed": result.changed, "errors": result.errors}


async def run_groups(ctx: RunContext) -> dict:
    """Apply a plan given by the user (editor) or derived from their request."""
    _require_supported(ctx)
    payload = ctx.run.payload or {}
    await ctx.step("Читаю задачу", done=0, total=5)
    await ctx.snapshot(refresh=True, announce=True)

    if payload.get("plan") is not None:
        try:
            plan = normalize_plan(payload["plan"])
        except PlanError as e:
            raise PipelineError(f"план групп: {e}")
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
    lines.append("Каждая группа: COMPLETE_GROUP + first-failed (ICPC), все баллы группы — на одном тесте.")
    lines.append("")
    lines.append(result.report())
    if ctx.auto_build:
        lines.append("\nЗапускаю сборку пакета.")
    await ctx.say("\n".join(lines), intent="groups", changed=result.changed, errors=result.errors,
                  plan=plan.to_dict())
    return {"build": True, "changed": result.changed, "errors": result.errors}
