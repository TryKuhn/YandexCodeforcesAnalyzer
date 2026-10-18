"""A chat message: the router decides what the user wants, the main model does it.

* the router (Haiku 5.5, Sonnet 5.5 as fallback) returns the intent and the
  minimal set of targets;
* ``question``/``chat`` -> an answer from the main model;
* ``modify`` -> tagged edits from the main model, applied only within the
  targets (plus the companion target a change can't live without);
* ``groups`` -> a test plan built from the message and applied;
* ``generate`` -> the whole-problem pipeline with the message as the idea;
* ``build`` -> the runner chains a build run.

Every model gets the full problem materials.
"""
from __future__ import annotations

import logging

from authoring.llm import prompts
from authoring.llm.client import LLMError, parse_json
from authoring.llm.models import ROUTER_MODELS
from authoring.llm.protocol import TARGETS, parse
from authoring.models import Message
from authoring.pipeline.apply import apply_edits
from authoring.pipeline.context import PipelineError, RunContext
from authoring.pipeline.generate import make_plan, run_generate
from authoring.pipeline.plan_apply import apply_plan

logger = logging.getLogger(__name__)

INTENTS = ("question", "modify", "generate", "groups", "build", "chat")

# a change in the first target is useless without the second one
COMPANIONS = {"generator": {"script"}, "script": {"generator"}}

# UI file context -> target
CONTEXT_TARGETS = {
    "solution": "solution", "validator": "validator", "checker": "checker", "interactor": "interactor",
    "generator": "generator", "script": "script", "statement": "statement",
}


async def route(ctx: RunContext, dossier: str, history: list[dict], text: str, context: dict | None) -> dict:
    """Intent + targets; falls back to the main model if both router models fail."""
    messages = prompts.router_messages(dossier, history, text, context)
    try:
        completion = await ctx.llm.complete_any(
            [*ROUTER_MODELS, ctx.model], messages, json_mode=True, max_tokens=1000
        )
        data = parse_json(completion.text)
    except LLMError as e:
        logger.warning("router failed: %s", e.message)
        data = {"intent": "question", "targets": [], "summary": ""}

    intent = str(data.get("intent") or "question").lower()
    if intent not in INTENTS:
        intent = "question"
    targets = [t for t in (data.get("targets") or []) if t in TARGETS]
    if intent == "modify" and not targets and context:
        hint = CONTEXT_TARGETS.get(str(context.get("file_role") or context.get("scope") or ""))
        if hint:
            targets = [hint]
    return {"intent": intent, "targets": targets, "summary": str(data.get("summary") or "")}


def allowed_targets(targets: list[str], *, with_companions: bool = True) -> set[str]:
    """The targets plus what they cannot live without.

    With a groups plan the script is built from the plan (group ranges and
    points depend on it), so a generator fix does not get to rewrite it.
    """
    allowed = set(targets)
    if with_companions:
        for t in targets:
            allowed |= COMPANIONS.get(t, set())
    return allowed


def _has_content(snapshot: dict) -> bool:
    legend = any((st.get("legend") or "").strip() for st in (snapshot.get("statements") or {}).values())
    main = any(s.get("tag") == "MA" for s in (snapshot.get("solutions") or {}).values())
    return legend or main


async def run_chat(ctx: RunContext) -> dict:
    payload = ctx.run.payload or {}
    message_id = payload.get("message_id")
    message = await ctx.db.get(Message, message_id) if message_id else None
    text = (message.content if message else payload.get("text") or "").strip()
    context = payload.get("context") or {}
    if not text:
        raise PipelineError("пустое сообщение")

    await ctx.step("Читаю задачу")
    await ctx.snapshot(refresh=True, announce=True)
    dossier = await ctx.dossier()
    history = await ctx.history(before_id=message_id)

    await ctx.step("Разбираю запрос")
    decision = await route(ctx, dossier, history, text, context)
    intent, targets = decision["intent"], decision["targets"]
    meta = {"intent": intent, "targets": targets}

    if intent in ("question", "chat"):
        await ctx.step("Отвечаю")
        completion = await ctx.llm.complete(ctx.model, prompts.answer_messages(dossier, history, text))
        await ctx.say(completion.text.strip() or "(пустой ответ модели)", **meta)
        return {"intent": intent}

    if intent == "build":
        await ctx.say("Запускаю сборку пакета с проверкой.", **meta)
        return {"intent": intent, "build": True, "force_build": True}

    if intent == "generate" and _has_content(await ctx.snapshot()):
        # never rewrite a filled problem on a classifier's guess
        intent = "modify" if targets else "question"
        meta["intent"] = intent
        if intent == "question":
            await ctx.step("Отвечаю")
            completion = await ctx.llm.complete(ctx.model, prompts.answer_messages(dossier, history, text))
            note = ("\n\n_Задача уже заполнена, поэтому целиком я её не пересоздаю. Попросите изменить "
                    "конкретные части или создайте новую задачу._")
            await ctx.say((completion.text.strip() or "") + note, **meta)
            return {"intent": intent}

    if intent == "generate":
        ctx.run.payload = {**payload, "idea": text}
        generated = await run_generate(ctx)
        return {"intent": intent, **generated}

    if intent == "groups":
        await ctx.step("Составляю план групп")
        plan = await make_plan(ctx, text)
        result = await apply_plan(ctx, plan, step_offset=0, total=4 if plan.use_groups else 2)
        reply = (
            f"План применён: {len(plan.groups)} групп, сумма баллов {plan.total_points:g}. "
            "Каждая группа — COMPLETE_GROUP + first-failed, все баллы на одном тесте группы.\n\n"
            + result.report()
        )
        await ctx.say(reply, plan=plan.to_dict(), changed=result.changed, errors=result.errors, **meta)
        return {"intent": intent, "build": True, "changed": result.changed}

    # modify
    if not targets:
        await ctx.say(
            "Не понял, что именно изменить. Уточните, пожалуйста: условие, решение, генератор, валидатор, "
            "чекер, скрипт тестов или лимиты?",
            **meta,
        )
        return {"intent": intent}
    has_plan = bool(((ctx.session.settings or {}).get("groups_plan") or {}).get("use_groups"))
    allowed = allowed_targets(targets, with_companions=not has_plan)
    await ctx.step("Вношу изменения: " + ", ".join(sorted(allowed)))
    completion = await ctx.llm.complete(
        ctx.model, prompts.modify_messages(dossier, history, text, sorted(allowed), ctx.session.problem_type)
    )
    if completion.truncated:
        raise PipelineError("ответ модели обрезан по лимиту токенов, попробуйте сузить запрос")
    parsed = parse(completion.text)

    await ctx.step("Сохраняю изменения в Polygon")
    result = await apply_edits(
        ctx, parsed.edits, allowed=allowed, commit_message=f"AI: {decision['summary'] or text}"[:200]
    )
    if result.plans:
        result.errors.append("план групп из ответа модели не применён: опишите группы отдельным сообщением")
    reply = parsed.reply or ("Готово." if result.changed else "Изменений не потребовалось.")
    if parsed.warnings:
        result.errors += parsed.warnings
    if has_plan and "script" in result.targets:
        result.errors.append(
            "скрипт изменён вручную, а в задаче есть план групп: группы и баллы могли сбиться — "
            "примените план групп заново (вкладка «Тесты»)"
        )
    report = result.report()
    build = result.needs_build and ctx.auto_build
    if build:
        report += "\n\nЗапускаю сборку пакета."
    await ctx.say(
        reply + ("\n\n" + report if report else ""),
        changed=result.changed, dropped=result.dropped, errors=result.errors, **meta,
    )
    return {"intent": intent, "build": build, "changed": result.changed}
