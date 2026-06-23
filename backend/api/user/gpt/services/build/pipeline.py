"""Full from-scratch upload+build pipeline (wizard path).

Orchestrates: settings → statement → examples → tags → groups setup →
technical files (per-file upload-time 3-retry) → package build (build-time
auto-repair lives in package_loop). Replaces the monolithic
``run_upload_pipeline``; all Polygon I/O goes through the sync layer or the
polygon wrappers, all AI through the generation/build services.
"""
import logging
import traceback

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.build import fix_gen, package_loop
from api.user.gpt.services.build.scoring_groups import setup_groups_and_points
from api.user.gpt.services.files.file_registry import applicable_types
from api.user.gpt.services.sessions import (append_chat_log, chat_message,
                                            update_session)
from api.user.gpt.services.sync.file_sync import ensure_problem, sync_file
from api.user.gpt.services.sync.settings_sync import sync_settings, sync_tags
from api.user.gpt.services.sync.statement_sync import sync_statement
from api.user.polygon.files.test.post.save_test import save_test
from api.user.polygon.problem.post.commit import commit_changes
from app.database import Session
from models.task.session import PipelineStage, ProblemType, TaskSession

logger = logging.getLogger(__name__)

MAX_UPLOAD_RETRIES = 3


async def _upload_examples(problem_id: int, user_id: int, examples: list,
                           db: AsyncSession) -> None:
    """Save each example as a statement test (1-indexed), logging upload failures."""
    for i, ex in enumerate(examples, start=1):
        try:
            await save_test(
                problem_id=problem_id,
                testset="tests",
                test_index=i,
                test_input=ex.get("input", ""),
                test_use_in_statements=True,
                user_id=user_id,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Failed to upload example test {i}: {e}")


async def _upload_tech_files(db: AsyncSession, session: TaskSession,
                             statement: dict, set_step) -> dict:
    """Push every applicable technical file, with a 3-attempt AI repair on
    upload-time failures. Returns {file_type: error_info} for files that could
    not be uploaded.
    """
    contents = await get_all_file_contents(db, session.id)
    upload_errors: dict = {}

    for file_type in applicable_types(session.problem_type):
        code = contents.get(file_type)
        if not code:
            continue

        await set_step(f"Загрузка {file_type}...")
        prev_errors: list[str] = []
        for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
            try:
                await sync_file(db, session, file_type, code, polygon_commit=False)
                break
            except Exception as e:
                err = str(e)
                logger.warning(
                    f"[{session.id}] upload {file_type} attempt {attempt} failed: {err}"
                )
                if attempt < MAX_UPLOAD_RETRIES:
                    await set_step(
                        f"Ошибка в {file_type}, ИИ правит "
                        f"(попытка {attempt}/{MAX_UPLOAD_RETRIES})..."
                    )
                    try:
                        code = await fix_gen.fix(
                            file_type, code, err, statement, session.model,
                            previous_errors=prev_errors or None,
                        )
                        prev_errors.append(err)
                    except Exception as fix_err:
                        logger.warning(f"[{session.id}] AI fix failed: {fix_err}")
                else:
                    upload_errors[file_type] = {
                        "error": err, "needs_manual_fix": True,
                    }
    return upload_errors


async def run_full_build(session_id: str) -> None:
    """Background entry: build the whole problem on Polygon from session state.

    Output-only problems force ``enable_points`` on, since they are always scored
    by the scorer-as-checker.
    """
    async with Session() as db:
        session = await db.get(TaskSession, session_id)
        if not session:
            return

        progress = {"status": "uploading", "current_step": "Создание задачи в Polygon...",
                    "error": None}

        async def set_step(step: str) -> None:
            progress["current_step"] = step
            await update_session(db, session_id, {"progress": progress})

        await update_session(
            db, session_id, {"progress": progress, "stage": PipelineStage.UPLOADING}
        )

        try:
            statement = session.statement or {}
            problem_settings = dict(session.problem_settings or {})
            examples = session.examples or []

            if session.problem_type == ProblemType.OUTPUT_ONLY:
                problem_settings["enable_points"] = True

            problem_id = await ensure_problem(db, session)

            await set_step("Настройка параметров задачи...")
            if problem_settings:
                await sync_settings(db, session, problem_settings, polygon_commit=False)

            await set_step("Загрузка условия...")
            await sync_statement(db, session, statement, polygon_commit=False)

            if examples:
                await set_step("Загрузка примеров...")
                await _upload_examples(problem_id, session.user_id, examples, db)

            if problem_settings.get("tags"):
                await set_step("Загрузка тегов...")
                await sync_tags(db, session, problem_settings["tags"], polygon_commit=False)

            await set_step("Настройка групп и баллов...")
            scoring_groups = await setup_groups_and_points(
                session_id, problem_id, session.user_id, problem_settings,
                statement.get("scoring"), db,
                subtasks=problem_settings.get("subtasks") or [],
            )

            upload_errors = await _upload_tech_files(db, session, statement, set_step)
            if upload_errors:
                await update_session(db, session_id, {"upload_errors": upload_errors})

            await set_step("Коммит изменений...")
            await commit_changes(
                problem_id, session.user_id, db,
                minor_changes=True, message="ai-generated task",
            )

            result = await package_loop.build_and_poll(
                db, session, scoring_groups=scoring_groups or None, set_step=set_step,
            )
            await _apply_build_result(db, session_id, problem_id, progress, result)

        except Exception as e:
            logger.exception(f"[{session_id}] Build pipeline failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            progress["traceback"] = traceback.format_exc()
            await update_session(
                db, session_id, {"progress": progress, "stage": PipelineStage.FAILED}
            )


def _format_range(indices: list) -> str:
    """Compact a sorted index list into ranges: [1,2,3,5] → '1-3, 5'."""
    if not indices:
        return "—"
    nums = sorted(int(i) for i in indices)
    parts, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if start != prev else f"{start}")
        start = prev = n
    parts.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ", ".join(parts)


async def _apply_build_result(db: AsyncSession, session_id: str, problem_id: int,
                              progress: dict, result: dict) -> None:
    """Translate package_loop's result into session stage + chat log.

    On ``done`` reports the Polygon/package ids and per-group test ranges;
    ``manual_fix``/``timeout`` escalate to the user with the raw build error.
    """
    status = result.get("status")

    if status == "done":
        progress["status"] = "done"
        progress["current_step"] = (
            f"Задача создана! Polygon ID: {problem_id}, "
            f"Package: {result.get('package_id')}"
        )
        await update_session(
            db, session_id,
            {"progress": progress, "stage": PipelineStage.DONE,
             "package_id": result.get("package_id")},
        )
        group_map = result.get("group_map") or {}
        msg = f"✅ Задача успешно собрана на Polygon. ID: {problem_id}."
        if group_map:
            lines = [
                f"  • Группа {g}: тесты {_format_range(idx)}"
                for g, idx in sorted(group_map.items(), key=lambda kv: str(kv[0]))
            ]
            msg += "\n\nРаспределение тестов по группам:\n" + "\n".join(lines)
        await append_chat_log(db, session_id, [chat_message("system", msg)])
        return

    error = result.get("error", "Неизвестная ошибка сборки")
    offender = result.get("offender")
    progress["status"] = "waiting_manual_fix"
    progress["current_step"] = "Ошибка сборки пакета"
    progress["error"] = error
    upload_errors = {"package": {"error": error, "needs_manual_fix": True}}
    if offender:
        upload_errors[offender] = {"error": error, "needs_manual_fix": True}
    await update_session(
        db, session_id,
        {"progress": progress, "stage": PipelineStage.FIXING_ERRORS,
         "upload_errors": upload_errors},
    )
    msg = (f"❌ Не удалось собрать пакет после автоматических попыток. "
           f"Ошибка: {error}")
    await append_chat_log(db, session_id, [chat_message("system", msg)])
