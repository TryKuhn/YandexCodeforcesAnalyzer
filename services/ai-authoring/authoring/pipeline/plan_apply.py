"""Turning a test plan into a working testset on Polygon.

1. (groups) the validator learns the per-group constraints (``validator.group()``);
2. one generator per generator name of the plan;
3. the FreeMarker script built from the plan;
4. groups, ``COMPLETE_GROUP`` + ``ICPC``, dependencies, all points on one test;
5. (groups) the «Система оценки» section of the statement.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from authoring.llm import prompts
from authoring.llm.protocol import FileEdit, StatementEdit, single_file
from authoring.pipeline.apply import ApplyResult, apply_edits
from authoring.pipeline.context import PipelineError, RunContext
from authoring.pipeline.groups import PlanError, TestPlan, assign, build_script, expand_lines, scoring_section
from authoring.polygon.client import PolygonError

logger = logging.getLogger(__name__)

TESTS_WAIT_ATTEMPTS = 6
TESTS_WAIT_SECONDS = 2.0
_GENERATOR_CONCURRENCY = 3
_POINTS_CONCURRENCY = 4


async def _generate_file(
    ctx: RunContext, system: str, task: str, *, role: str, name: str, dossier: str | None = None
) -> FileEdit:
    """One file from the main model; pass ``dossier`` when calling concurrently
    (the DB session behind :meth:`RunContext.dossier` is not concurrency-safe)."""
    if dossier is None:
        dossier = await ctx.dossier()
    completion = await ctx.llm.complete(ctx.model, prompts.file_messages(system, dossier, task))
    if completion.truncated:
        raise PipelineError(f"{name}: ответ модели обрезан по лимиту токенов")
    edit = single_file(completion.text, role=role)
    edit.role, edit.name = role, name
    return edit


async def write_generators(ctx: RunContext, plan: TestPlan) -> ApplyResult:
    by_generator: dict[str, list[dict]] = {}
    for g in plan.generated_groups:
        assert g.generator
        by_generator.setdefault(g.generator, []).append(g.to_dict())

    semaphore = asyncio.Semaphore(_GENERATOR_CONCURRENCY)
    plan_json = prompts.plan_text(plan.to_dict())
    dossier = await ctx.dossier()

    async def one(name: str, groups: list[dict]) -> FileEdit:
        async with semaphore:
            task = prompts.generator_task(name, groups) + f"\n\nВесь план тестов:\n{plan_json}"
            return await _generate_file(
                ctx, prompts.generator_system(), task, role="generator", name=f"{name}.cpp", dossier=dossier
            )

    edits = await asyncio.gather(*(one(n, gs) for n, gs in by_generator.items()))
    return await apply_edits(ctx, list(edits), allowed={"generator"})


async def update_validator_for_groups(ctx: RunContext, plan: TestPlan) -> ApplyResult:
    snapshot = await ctx.snapshot()
    name = snapshot.get("validator") or "validator.cpp"
    task = prompts.VALIDATOR_GROUPS_TASK + "\n\nПлан:\n" + prompts.plan_text(plan.to_dict())
    edit = await _generate_file(ctx, prompts.VALIDATOR_SYSTEM, task, role="validator", name=name)
    return await apply_edits(ctx, [edit], allowed={"validator"})


def _differs(current: Any, wanted: float) -> bool:
    return current is None or float(current) != float(wanted)


async def _wait_for_tests(ctx: RunContext, expected: int) -> list[dict]:
    tests: list[dict] = []
    for _ in range(TESTS_WAIT_ATTEMPTS):
        tests = await ctx.client.tests(ctx.session.polygon_id)
        if sum(1 for t in tests if not t.get("manual")) >= expected:
            return tests
        await asyncio.sleep(TESTS_WAIT_SECONDS)
    return tests


async def setup_testset(ctx: RunContext, plan: TestPlan) -> ApplyResult:
    """Script + groups + points (no model calls)."""
    result = ApplyResult()
    client, pid = ctx.client, ctx.session.polygon_id
    lines = expand_lines(plan)

    await client.save_script(pid, build_script(plan))
    result.changed.append("скрипт тестов")
    result.targets.add("script")
    ctx.invalidate()

    tests = await _wait_for_tests(ctx, len(lines))
    try:
        assignment = assign(plan, tests, lines)
    except PlanError as e:
        raise PipelineError(str(e))
    result.errors += assignment.warnings

    if not plan.use_groups:
        if any(t.get("group") for t in tests):
            await client.enable_groups(pid, False)
            result.changed.append("группы выключены")
        return result

    if plan.total_points > 0:
        await client.enable_points(pid, True)
    await client.enable_groups(pid, True)
    for name, indices in assignment.groups.items():
        if indices:
            await client.set_test_group(pid, name, indices)
    for name, (points_policy, feedback, deps) in assignment.policies.items():
        if assignment.groups.get(name):
            await client.save_group(
                pid, name, points_policy=points_policy, feedback_policy=feedback, dependencies=deps
            )

    if plan.total_points > 0:
        # unknown (None) points are set explicitly too
        current = {t["index"]: t.get("points") for t in tests}
        semaphore = asyncio.Semaphore(_POINTS_CONCURRENCY)

        async def set_points(index: int, points: float) -> None:
            async with semaphore:
                await client.save_test(pid, index, test_points=points)

        await asyncio.gather(*(
            set_points(i, p) for i, p in assignment.points.items() if _differs(current.get(i), p)
        ))

    summary = "; ".join(
        f"{g.name}: {len(assignment.groups[g.name])} т., {g.points:g} б." for g in plan.groups
    )
    result.changed.append(f"группы ({summary})")
    result.targets.add("groups")
    return result


async def apply_plan(ctx: RunContext, plan: TestPlan, *, step_offset: int = 0, total: int | None = None) -> ApplyResult:
    """Validator (groups) -> generators -> script/groups/points -> scoring section."""
    result = ApplyResult()
    settings = dict(ctx.session.settings or {})
    settings["groups_plan"] = plan.to_dict()
    ctx.session.settings = settings
    await ctx.db.commit()

    steps = 4 if plan.use_groups else 2
    total = total or steps
    n = step_offset

    if plan.use_groups:
        n += 1
        await ctx.step("Валидатор: проверки ограничений групп", done=n, total=total)
        result.merge(await update_validator_for_groups(ctx, plan))

    n += 1
    names = sorted({g.generator for g in plan.generated_groups if g.generator})
    await ctx.step(f"Генераторы: {', '.join(names)}", done=n, total=total)
    generators = await write_generators(ctx, plan)
    result.merge(generators)
    if generators.errors:
        raise PipelineError("не удалось загрузить генераторы: " + "; ".join(generators.errors))

    n += 1
    await ctx.step("Скрипт FreeMarker, группы и баллы", done=n, total=total)
    try:
        result.merge(await setup_testset(ctx, plan))
    except PolygonError as e:
        raise PipelineError(f"настройка тестов: {e.message}")

    if plan.use_groups:
        n += 1
        await ctx.step("Раздел «Система оценки» в условии", done=n, total=total)
        snapshot = await ctx.snapshot(refresh=True)
        langs = list((snapshot.get("statements") or {}).keys()) or ["russian"]
        # the table is in Russian, so it goes to the Russian statement only
        lang = "russian" if "russian" in langs else langs[0]
        edit = StatementEdit(lang, "scoring", scoring_section(plan))
        result.merge(await apply_edits(ctx, [edit], allowed={"statement"}))

    try:
        await ctx.client.commit(ctx.session.polygon_id, "AI: test plan applied")
    except PolygonError as e:
        result.errors.append(f"commit: {e.message}")
    ctx.invalidate()
    return result
