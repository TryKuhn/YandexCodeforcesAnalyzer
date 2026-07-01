"""Execute a 'modify' intent: change the statement/file(s) and sync to Polygon.

Three branches by resolved scope:
  statement → regenerate the statement, push it, then run the essence cascade
              (regenerate dependent files on the NEW statement and sync them).
  file      → refine exactly one file with its own prompt and sync it.
  task      → let the model pick & rewrite the relevant files, then sync them.

Every change is pushed to Polygon immediately (file_sync auto-creates the
problem if it does not exist yet). Package rebuild is NOT triggered here.
"""
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.chat import essence_checker
from api.user.gpt.services.chat.context_resolver import ResolvedContext
from api.user.gpt.services.generation import (file_gen, samples_gen, statement_gen,
                                              subtask_plan_gen,
                                              subtask_solutions_gen)
from api.user.gpt.services.llm.client import llm, strip_code_fences
from api.user.gpt.services.llm.models import SCAFFOLD_MODEL
from api.user.gpt.services.prompts import problem_type as problem_type_guide
from api.user.gpt.services.prompts import task_modify
from api.user.gpt.services.sessions import is_interactive, now_utc, update_session
from api.user.gpt.services.sync import file_sync, samples_sync, statement_sync
from models.task.session import ProblemType, TaskSession

logger = logging.getLogger(__name__)

_FILE_LABELS = {
    "validator": "validator.cpp", "generator": "generator.cpp",
    "checker": "checker.cpp", "interactor": "interactor.cpp",
    "scorer": "scorer.cpp", "jury_answer": "jury.cpp",
    "solution_cpp": "solution.cpp", "solution_py": "solution.py",
    "wa_sol": "wa.cpp", "tl_sol": "tl.cpp", "re_sol": "re.cpp",
    "ml_sol": "ml.cpp", "script": "script.txt",
}


_VALID_FILE_TYPES = set(_FILE_LABELS)


def _label(key: str) -> str:
    """Return the human filename label for a file type key."""
    return _FILE_LABELS.get(key, key)


async def execute(
    db: AsyncSession, session: TaskSession, message: str, resolved: ResolvedContext
) -> dict:
    """Dispatch a modify intent to the statement/file/task branch by scope."""
    if resolved.scope == "statement":
        return await _modify_statement(db, session, message)
    if resolved.scope == "file" and resolved.file_key:
        return await _modify_file(db, session, message, resolved.file_key)
    return await _modify_task(db, session, message)


async def _modify_statement(db: AsyncSession, session: TaskSession, message: str) -> dict:
    """Regenerate + push the statement, then cascade-regenerate dependents.

    Sections the regen may drop (interaction/scoring) are carried over from the
    old statement. The essence check decides which already-existing dependent
    files must be regenerated against the new statement and synced.
    """
    old_statement = dict(session.statement or {})

    history = list(session.history or [])
    if session.statement:
        history.append({"role": "assistant",
                        "content": json.dumps(session.statement, ensure_ascii=False)})
    history.append({"role": "user", "content": message})

    new_stmt = await statement_gen.generate(
        user_idea=message, model=session.model,
        user_prompt=session.system_prompt, history=history,
        problem_type=session.problem_type,
    )
    for section in ("interaction", "scoring"):
        if old_statement.get(section) and not new_stmt.get(section):
            new_stmt[section] = old_statement[section]

    session.history = history
    session.statement = new_stmt
    flag_modified(session, "statement")
    session.updated_at = now_utc()
    await db.commit()

    await statement_sync.sync_statement(db, session, new_stmt)

    updated_files: list[str] = []
    essence = await essence_checker.check(old_statement, new_stmt)
    if essence.get("essence_changed"):
        existing = set((await get_all_file_contents(db, session.id)).keys())
        targets = [ft for ft in essence.get("dependents", []) if ft in existing]
        interactive = is_interactive(session)
        regenerated = []
        for ft in targets:
            try:
                code = await file_gen.regenerate(ft, new_stmt, session.model, interactive,
                                                 problem_type=session.problem_type)
                regenerated.append((ft, code))
            except Exception as e:
                logger.warning(f"[{session.id}] regenerate {ft} failed: {e}")
        if regenerated:
            updated_files = await file_sync.sync_files(db, session, regenerated)

    if updated_files:
        msg = (f"Обновил условие и зависимые файлы: "
               f"{', '.join(_label(k) for k in updated_files)}.")
    else:
        msg = "Обновил условие задачи."
    return {
        "response": msg,
        "updated_files": updated_files,
        "statement": new_stmt,
        "technical_data": None,
        "synced": True,
    }


async def _modify_file(db: AsyncSession, session: TaskSession, message: str,
                       file_key: str) -> dict:
    """Refine exactly one file (or generate it from scratch if empty) and sync."""
    files = await get_all_file_contents(db, session.id)
    current = files.get(file_key, "")
    interactive = is_interactive(session)

    if current.strip():
        new_code = await file_gen.refine(
            file_type=file_key, current_code=current, feedback=message,
            statement=session.statement or {}, model=session.model, interactive=interactive,
            problem_type=session.problem_type,
        )
        verb = "обновлён"
    else:
        new_code = await file_gen.generate(
            file_key, session.statement or {}, session.model, interactive,
            problem_type=session.problem_type,
        )
        verb = "сгенерирован"

    await file_sync.sync_file(db, session, file_key, new_code)
    return {
        "response": f"{_label(file_key)} {verb} и синхронизирован с Polygon.",
        "updated_files": [file_key],
        "statement": None,
        "technical_data": {file_key: new_code},
        "synced": True,
    }


async def regenerate(db: AsyncSession, session: TaskSession, message: str) -> dict:
    """Public entry for the 'regenerate the whole task' action (intent router)."""
    return await _generate_from_scratch(db, session, message, redo=bool(session.statement))


async def _modify_task(db: AsyncSession, session: TaskSession, message: str) -> dict:
    """Let the model pick & rewrite the relevant files, then sync them.

    Empty problem generates from scratch; statement-but-no-files generates the
    file pack. The model may create missing files (e.g. an absent solution), so
    any valid file type is accepted, not only files that already exist.
    """
    files = await get_all_file_contents(db, session.id)

    if not session.statement:
        return await _generate_from_scratch(db, session, message)
    if not files:
        return await _generate_pack(db, session)

    try:
        result = await llm.ask(
            session.model,
            [
                {"role": "system",
                 "content": f"{problem_type_guide.guide(session.problem_type)}\n\n"
                            f"{task_modify.SYSTEM_PROMPT}"},
                {"role": "user",
                 "content": task_modify.build_user_prompt(session.statement or {}, files, message)},
            ],
            json_mode=True,
        )
    except Exception:
        return {"response": "Не понял запрос как изменение файлов. Уточните, что "
                            "изменить, или выберите конкретный файл в контексте чата.",
                "updated_files": [], "statement": None, "technical_data": None,
                "synced": False}
    changed = {
        k: strip_code_fences(v)
        for k, v in result.items()
        if isinstance(v, str) and v.strip() and (k in files or k in _VALID_FILE_TYPES)
    }
    if not changed:
        return {"response": "Не нашёл, что изменить. Уточните запрос.",
                "updated_files": [], "statement": None, "technical_data": None,
                "synced": False}

    updated_files = await file_sync.sync_files(db, session, list(changed.items()))
    return {
        "response": f"Обновлено и синхронизировано: "
                    f"{', '.join(_label(k) for k in updated_files)}.",
        "updated_files": updated_files,
        "statement": None,
        "technical_data": changed,
        "synced": True,
    }


def _groups_enabled(session: TaskSession) -> bool:
    """True when the session enables subtask groups or per-test points."""
    s = session.problem_settings or {}
    return bool(s.get("enable_groups") or s.get("enable_points"))


_GEN_TOTAL = 4


async def _gen_progress(db: AsyncSession, session_id: str, step: str, idx: int) -> None:
    """Persist a generation-stage progress update (polled by the chat UI).

    Commits ``session.progress`` so the synchronous /ai/chat request's stages are
    visible to the separate polling request while generation is in flight.
    """
    await update_session(db, session_id, {"progress": {
        "status": "generating", "current_step": step,
        "step": idx, "total": _GEN_TOTAL, "error": None,
    }})


async def _prepare_samples(db: AsyncSession, session: TaskSession, stmt: dict) -> bool:
    """Generate 1-3 manual samples, store them, and push them as sample tests.

    Done before the generator so the participant has concrete examples; with
    groups enabled they go to group 0 (no points). Returns True only when the
    samples were both generated AND uploaded to Polygon — a Polygon upload
    failure is logged and reported (not raised), so it no longer silently
    leaves the problem with no sample tests.
    """
    try:
        examples = await samples_gen.generate(stmt, session.model, count=3)
    except Exception as e:
        logger.warning(f"[{session.id}] sample generation failed: {e}")
        return False
    if not examples:
        logger.warning(f"[{session.id}] sample generation returned no examples")
        return False
    indexed = [
        {"index": i + 1, "input": ex["input"], "output": ex["output"]}
        for i, ex in enumerate(examples)
    ]
    session.examples = indexed
    flag_modified(session, "examples")
    session.updated_at = now_utc()
    await db.commit()

    try:
        problem_id = await file_sync.ensure_problem(db, session)
        await samples_sync.upload_examples(
            db, problem_id, session.user_id, indexed,
            group="0" if _groups_enabled(session) else None,
        )
    except Exception as e:
        logger.warning(f"[{session.id}] sample upload to Polygon failed: {e}")
        return False
    return True


async def _prepare_subtasks(db: AsyncSession, session: TaskSession, stmt: dict) -> dict:
    """Plan subtasks + render the scoring table into the statement (groups path)."""
    if session.problem_type == ProblemType.OUTPUT_ONLY or not _groups_enabled(session):
        return stmt
    await _gen_progress(db, session.id, "Планирую подзадачи и баллы…", 2)
    # Subtask plan is internal scaffolding → cheap/fast model, not the main one.
    subtasks = await subtask_plan_gen.generate(stmt, SCAFFOLD_MODEL)
    if not subtasks:
        return stmt

    settings = dict(session.problem_settings or {})
    settings["subtasks"] = subtasks
    settings["enable_groups"] = True
    settings["enable_points"] = True
    session.problem_settings = settings
    flag_modified(session, "problem_settings")

    stmt = dict(stmt)
    stmt["scoring"] = subtask_plan_gen.render_scoring_latex(subtasks)
    session.statement = stmt
    flag_modified(session, "statement")
    session.updated_at = now_utc()
    await db.commit()
    await statement_sync.sync_statement(db, session, stmt)
    return stmt


async def _generate_from_scratch(db: AsyncSession, session: TaskSession,
                                 message: str, redo: bool = False) -> dict:
    """Generate a full problem (statement + file pack) from a description.

    Used both for an empty problem and for a "переделай полностью" redo (the new
    pack overwrites the existing files by file_type).
    """
    await _gen_progress(db, session.id, "Генерирую условие задачи…", 1)
    stmt = await statement_gen.generate(
        user_idea=message, model=session.model,
        user_prompt=session.system_prompt, history=[],
        problem_type=session.problem_type,
    )
    session.statement = stmt
    flag_modified(session, "statement")
    session.updated_at = now_utc()
    await db.commit()
    await statement_sync.sync_statement(db, session, stmt)

    stmt = await _prepare_subtasks(db, session, stmt)

    pack_result = await _generate_pack(db, session, statement=stmt)
    files_part = (f" и файлы: {', '.join(_label(k) for k in pack_result['updated_files'])}"
                  if pack_result["updated_files"] else "")
    verb = "Пересоздал" if redo else "Создал"
    response = (f"{verb} задачу «{stmt.get('name', '')}»: условие{files_part}. "
                f"Синхронизировано с Polygon.")

    # Surface what did NOT make it to Polygon instead of silently dropping it
    # (the per-file Polygon error is in the backend logs at WARNING).
    warns: list[str] = []
    if pack_result.get("failed"):
        warns.append("Не синхронизировались с Polygon (перегенерируйте по "
                     f"отдельности): {', '.join(_label(k) for k in pack_result['failed'])}.")
    if not pack_result.get("samples_ok"):
        warns.append("Примеры (семплы) не созданы — без них и без скрипта тесты "
                     "не сгенерируются. Попробуйте ещё раз или проверьте логи.")
    if warns:
        response += "\n" + "\n".join(warns)

    return {
        "response": response,
        "updated_files": ["statement"] + pack_result["updated_files"],
        "statement": stmt,
        "technical_data": pack_result["technical_data"],
        "synced": True,
        "build": bool(pack_result["updated_files"]),
    }


async def _sync_script_with_retry(
    db: AsyncSession, session: TaskSession, script_code: str, stmt: dict,
    max_attempts: int = 2,
) -> tuple[bool, str]:
    """Save the test script, regenerating it on a Polygon validation error.

    Polygon rejects e.g. duplicate test commands ('Test #X coincides with #Y') at
    save time. We feed that exact error back to the model and retry so the
    problem actually gets a working script (and therefore generated tests).
    Returns (synced, final_script_code).
    """
    code = script_code
    for attempt in range(max_attempts):
        try:
            await file_sync.sync_file(db, session, "script", code)
            return True, code
        except Exception as e:
            logger.warning(f"[{session.id}] script sync attempt {attempt + 1} failed: {e}")
            if attempt + 1 >= max_attempts:
                return False, code
            try:
                code = await file_gen.refine(
                    "script", code,
                    f"Polygon отклонил скрипт с ошибкой: {e}. Исправь так, чтобы "
                    "КАЖДАЯ итоговая команда генерации была УНИКАЛЬНОЙ — различай "
                    "повторяющиеся через -seed=${i} (генератор обязан читать seed).",
                    stmt, session.model, problem_type=session.problem_type,
                )
            except Exception as gen_err:
                logger.warning(f"[{session.id}] script regenerate failed: {gen_err}")
                return False, code
    return False, code


async def _generate_pack(db: AsyncSession, session: TaskSession,
                         statement: dict | None = None) -> dict:
    """Generate every file applicable to the problem type and sync them.

    With groups enabled, the script emits tests grouped by subtask and a partial
    solution is generated for each non-final subtask (tagged with its expected
    full-testset verdict), registered in ``solution_meta`` so the sync layer
    routes them as solutions.
    """
    stmt = statement if statement is not None else (session.statement or {})

    samples_ok = bool(session.examples)
    if not session.examples:
        await _gen_progress(db, session.id, "Генерирую примеры (семплы)…", 3)
        samples_ok = await _prepare_samples(db, session, stmt)

    settings = session.problem_settings or {}
    subtasks = settings.get("subtasks") if _groups_enabled(session) else None

    await _gen_progress(
        db, session.id,
        "Генерирую файлы (валидатор, генератор, чекер, решения)…", 4,
    )
    pack, skipped = await file_gen.generate_pack(
        session.problem_type, stmt, session.model, subtasks=subtasks,
    )
    if not pack:
        return {"response": "Не удалось сгенерировать файлы.", "updated_files": [],
                "statement": None, "technical_data": None, "synced": False}

    if subtasks:
        try:
            partials, sub_skipped = await subtask_solutions_gen.generate(
                stmt, session.model, subtasks, problem_type=session.problem_type,
            )
        except Exception as e:
            logger.warning(f"[{session.id}] subtask solutions failed: {e}")
            partials, sub_skipped = [], {}
        skipped = {**skipped, **sub_skipped}
        if partials:
            meta = dict(session.solution_meta or {})
            for p in partials:
                pack[p["file_type"]] = p["code"]
                meta[p["file_type"]] = {"tag": p["tag"], "name": p["name"]}
            session.solution_meta = meta
            flag_modified(session, "solution_meta")
            session.updated_at = now_utc()
            await db.commit()

    # The script is synced separately with a retry: Polygon validates it on save
    # (e.g. rejects duplicate test commands), so on failure we regenerate it with
    # the exact Polygon error and try again — otherwise the problem ends up with
    # no test script and the package build produces zero tests.
    script_code = pack.get("script")
    non_script = [(k, v) for k, v in pack.items() if k != "script"]
    updated_files = await file_sync.sync_files(db, session, non_script)
    if script_code:
        ok, final_script = await _sync_script_with_retry(db, session, script_code, stmt)
        pack["script"] = final_script
        if ok:
            updated_files.append("script")

    failed = [ft for ft in pack if ft not in updated_files]
    msg = (f"Сгенерированы и синхронизированы файлы: "
           f"{', '.join(_label(k) for k in updated_files)}.")
    if failed:
        msg += (f"\nНе удалось синхронизировать: {', '.join(_label(k) for k in failed)} "
                f"— попробуйте перегенерировать их по отдельности.")
    if skipped:
        lines = "\n".join(f"  • {_label(k)}: {reason}" for k, reason in skipped.items())
        msg += ("\n\nНе добавил некоторые решения — для них не удалось гарантировать "
                f"нужный вердикт настоящим алгоритмом:\n{lines}")
    return {
        "response": msg,
        "updated_files": updated_files,
        "statement": None,
        "technical_data": pack,
        "synced": bool(updated_files),
        "build": bool(updated_files),
        "failed": failed,
        "samples_ok": samples_ok,
    }
