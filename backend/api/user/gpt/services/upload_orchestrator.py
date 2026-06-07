import asyncio
import logging
import re
import time
import traceback
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.user.gpt.services.ai_file_helpers import (get_session_files,
                                                   mark_uploaded,
                                                   upsert_ai_file)
from api.user.gpt.services.ai_service import TaskAIService
from api.user.polygon.files.checker.post.set_checker import set_checker
from api.user.polygon.files.generator.post.save_file import set_generator
from api.user.polygon.files.interactor.post.set_interactor import set_interactor
from api.user.polygon.files.script.post.save_script import save_script as set_script
from api.user.polygon.files.solution.post.save_solution import save_solution as set_solution
from api.user.polygon.files.test.post.save_test import save_test
from api.user.polygon.files.validator.post.set_validator import set_validator
from api.user.polygon.problem.get.packages import get_packages
from api.user.polygon.problem.post.commit import commit_changes as commit
from api.user.polygon.problem.post.create import create_problem
from api.user.polygon.problem.settings.enable_groups import enable_groups
from api.user.polygon.problem.settings.enable_points import enable_points
from api.user.polygon.problem.settings.save_test_group import save_test_group
from api.user.polygon.problem.settings.set_tags import set_tags
from api.user.polygon.problem.settings.set_test_group import set_test_group
from api.user.polygon.problem.settings.update_info import update_info
from api.user.polygon.statement.post.statement import save_statement
from app.database import Session
from models.task.session import TaskSession as AISession, PipelineStage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_BUILD_RETRIES = 2
PACKAGE_POLL_INTERVAL = 10
PACKAGE_POLL_TIMEOUT = 600

STEP_MAP: list[tuple[str, Callable[..., Any], str, str, list[str]]] = [
    ("validator", set_validator, "validator", "validator.cpp", []),
    ("generator", set_generator, "generator", "generator.cpp", []),
    ("checker", set_checker, "checker", "checker.cpp", []),
    ("sol_main", set_solution, "solution_cpp", "solution.cpp", ["MA"]),
    ("sol_py", set_solution, "solution_py", "solution_py.py", ["OK"]),
    ("sol_wa", set_solution, "wa_sol", "wa.cpp", ["WA"]),
    ("sol_tl", set_solution, "tl_sol", "tl.cpp", ["TL"]),
    ("sol_re", set_solution, "re_sol", "re.cpp", ["RE"]),
    ("sol_ml", set_solution, "ml_sol", "ml.cpp", ["ML"]),
]


def _parse_scoring_groups(scoring_latex: str | None) -> list[dict]:
    """Parse LaTeX scoring table into group config dicts.
    Returns list of {group, points, dependencies, feedback_policy}.
    Skips group 0 (sample tests with no points).
    """
    if not scoring_latex:
        return []

    tab_match = re.search(
        r"\\begin\{tabular\}(.*?)\\end\{tabular\}", scoring_latex, re.DOTALL
    )
    if not tab_match:
        return []

    inner = tab_match.group(1)
    inner = re.sub(r"^\s*\{[^}]*\}\s*", "", inner)

    def clean_cell(cell: str) -> str:
        cell = re.sub(r"\\textbf\s*\{\\scriptsize\s*\{([^}]*)\}\}", r"\1", cell)
        cell = re.sub(r"\\textbf\s*\{([^}]*)\}", r"\1", cell)
        cell = re.sub(r"\\scriptsize\s*\{([^}]*)\}", r"\1", cell)
        cell = re.sub(r"\$([^$]+)\$", r"\1", cell)
        cell = cell.replace("\\hline", "").strip()
        return cell

    rows = []
    for seg in inner.split("\\\\"):
        seg = seg.replace("\\hline", "").strip()
        if seg:
            rows.append([clean_cell(c) for c in seg.split("&")])

    if len(rows) < 2:
        return []

    groups = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        group_num = row[0].strip()
        points_str = row[1].strip()
        deps_str = row[3].strip()
        feedback_str = row[4].strip()

        if group_num == "0" or points_str == "--":
            continue

        try:
            points = int(float(re.sub(r"[^0-9.]", "", points_str) or "0"))
        except (ValueError, TypeError):
            continue

        deps = []
        if deps_str and deps_str != "--":
            for d in deps_str.split(","):
                d = d.strip()
                if d and d != "--":
                    deps.append(d)

        feedback = (
            "icpc"
            if ("первая" in feedback_str.lower() or "first" in feedback_str.lower())
            else "complete"
        )

        groups.append(
            {
                "group": group_num,
                "points": points,
                "dependencies": deps,
                "feedback_policy": feedback,
            }
        )

    return groups


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


async def _update_session(session_id: str, data: Dict, db: AsyncSession):
    await db.execute(update(AISession).where(AISession.id == session_id).values(**data))
    await db.commit()


async def _append_chat_log(session_id: str, entries: list, db: AsyncSession):
    session = await db.get(AISession, session_id)
    if not session:
        return
    log = list(session.chat_log or [])
    log.extend(entries)
    session.chat_log = log
    flag_modified(session, "chat_log")
    await db.commit()


def _make_polygon_name(model: str, statement: Dict, session_id: str) -> str:
    model_short = re.sub(r"[^a-z0-9]", "", model.split("/")[-1].lower())[:8]
    suffix = session_id[:4]
    timestamp = str(int(time.time()))[-5:]
    return f"{model_short}-task-{suffix}-{timestamp}"


def _build_step_map(session_files: dict, solution_meta: dict | None) -> list[tuple]:
    """Returns STEP_MAP extended with custom solutions from solution_meta."""
    steps = list(STEP_MAP)
    if not solution_meta:
        return steps
    for file_type, meta in solution_meta.items():
        if file_type in session_files:
            tag = meta.get("tag", "OK")
            name = meta.get("name", file_type)
            if not name.endswith(".cpp"):
                name += ".cpp"
            steps.append((f"custom_{file_type}", set_solution, file_type, name, [tag]))
    return steps


async def _upload_steps(
    session_id: str,
    problem_id: int,
    user_id: int,
    statement: Dict,
    model: str,
    progress: Dict,
    db: AsyncSession,
    solution_meta: dict | None = None,
    include_interactor: bool = False,
) -> dict:
    ai = TaskAIService()
    session_files = await get_session_files(db, session_id)
    upload_errors = {}

    step_map = _build_step_map(session_files, solution_meta)

    # Interactor (for interactive problems)
    if include_interactor:
        interactor_obj = session_files.get("interactor")
        if interactor_obj and not interactor_obj.uploaded:
            progress["current_step"] = "Загрузка interactor.cpp..."
            await _update_session(session_id, {"progress": progress}, db)
            try:
                await set_interactor(
                    problem_id, "interactor.cpp", interactor_obj.content, user_id, db
                )
                await mark_uploaded(db, session_id, "interactor")
                await db.commit()
            except Exception as e:
                upload_errors["interactor"] = {
                    "file_name": "interactor.cpp",
                    "error": str(e),
                    "needs_manual_fix": True,
                }

    for step_name, upload_func, data_key, file_name, extra_args in step_map:
        file_obj = session_files.get(data_key)
        if not file_obj:
            continue

        if file_obj.uploaded:
            logger.info(f"[{session_id}] Skipping already-uploaded {file_name}")
            continue

        code = file_obj.content
        progress["current_step"] = f"Загрузка {file_name}..."
        await _update_session(session_id, {"progress": progress}, db)

        success = False
        last_error = None
        error_history: list[str] = []

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                args = [problem_id, file_name, code, *extra_args, user_id, db]
                await upload_func(*args)
                success = True
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[{session_id}] {step_name} attempt {attempt} failed: {e}"
                )
                progress["retries"] = attempt
                progress["current_step"] = (
                    f"Ошибка в {file_name}, ИИ правит "
                    f"(попытка {attempt}/{MAX_RETRIES})..."
                )
                await _update_session(session_id, {"progress": progress}, db)

                if attempt < MAX_RETRIES:
                    try:
                        code = await ai.fix_code(
                            last_error,
                            step_name,
                            code,
                            statement,
                            model,
                            previous_errors=error_history if error_history else None,
                        )
                        error_history.append(last_error)
                        await upsert_ai_file(
                            db, session_id, data_key, code, uploaded=False
                        )
                        await db.commit()
                    except Exception as fix_err:
                        logger.warning(
                            f"[{session_id}] AI fix failed for {step_name}: {fix_err}"
                        )
                else:
                    error_history.append(last_error)

        if success:
            logger.info(f"[{session_id}] Uploaded {file_name}")
            await mark_uploaded(db, session_id, data_key)
            await db.commit()
        else:
            logger.error(
                f"[{session_id}] Failed to upload {file_name} after {MAX_RETRIES} attempts: {last_error}"
            )
            upload_errors[data_key] = {
                "file_name": file_name,
                "error": last_error,
                "needs_manual_fix": True,
            }

    # Script
    script_obj = session_files.get("script")
    if script_obj and not script_obj.uploaded:
        progress["current_step"] = "Загрузка скрипта тестов..."
        await _update_session(session_id, {"progress": progress}, db)
        try:
            await set_script(problem_id, "tests", script_obj.content, user_id, db)
            await mark_uploaded(db, session_id, "script")
            await db.commit()
        except Exception as e:
            logger.error(f"[{session_id}] Failed to upload script: {e}")
            upload_errors["script"] = {
                "file_name": "script.txt",
                "error": str(e),
                "needs_manual_fix": True,
            }

    return upload_errors


async def _setup_groups_and_points(
    session_id: str,
    problem_id: int,
    user_id: int,
    problem_settings: dict,
    scoring_latex: str | None,
    progress: Dict,
    db: AsyncSession,
) -> list[dict]:
    """Enable groups/points on the Polygon problem and configure each group.
    Returns parsed group configs for later test assignment.
    """
    enable_grp = problem_settings.get("enable_groups", False)
    enable_pts = problem_settings.get("enable_points", False)

    if not enable_grp and not enable_pts:
        return []

    groups = _parse_scoring_groups(scoring_latex)

    if enable_grp:
        try:
            progress["current_step"] = "Включение групп тестов..."
            await _update_session(session_id, {"progress": progress}, db)
            await enable_groups(problem_id, "tests", True, user_id, db)
            logger.info(f"[{session_id}] Groups enabled")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to enable groups: {e}")

    if enable_pts:
        try:
            progress["current_step"] = "Включение системы баллов..."
            await _update_session(session_id, {"progress": progress}, db)
            await enable_points(problem_id, True, user_id, db)
            logger.info(f"[{session_id}] Points enabled")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to enable points: {e}")

    for group_cfg in groups:
        try:
            await save_test_group(
                problem_id=problem_id,
                test_set="tests",
                group=group_cfg["group"],
                points=group_cfg["points"],
                points_policy="complete-group",
                feedback_policy=group_cfg["feedback_policy"],
                dependencies=group_cfg["dependencies"],
                user_id=user_id,
                db=db,
            )
            logger.info(
                f"[{session_id}] Configured group {group_cfg['group']} "
                f"({group_cfg['points']} pts, deps={group_cfg['dependencies']})"
            )
        except Exception as e:
            logger.warning(
                f"[{session_id}] Failed to configure group {group_cfg['group']}: {e}"
            )

    return groups


async def _assign_tests_to_groups(
    session_id: str,
    problem_id: int,
    user_id: int,
    groups: list[dict],
    progress: Dict,
    db: AsyncSession,
) -> None:
    """After package build, fetch test list and distribute tests to groups proportionally."""
    if not groups:
        return

    try:
        from api.user.polygon.files.test.get.tests import get_tests

        tests = await get_tests(problem_id, "tests", user_id, db)
        non_example_indices = sorted(
            t.get("index", 0) for t in tests if not t.get("useInStatements", False)
        )

        if not non_example_indices:
            logger.info(f"[{session_id}] No non-example tests to assign to groups")
            return

        total_pts = sum(g["points"] for g in groups)
        if total_pts == 0:
            return

        total = len(non_example_indices)
        assigned = 0
        for i, group_cfg in enumerate(groups):
            if i == len(groups) - 1:
                count = total - assigned
            else:
                count = max(1, round(total * group_cfg["points"] / total_pts))

            slice_indices = non_example_indices[assigned : assigned + count]
            assigned += count

            if slice_indices:
                indices_str = ",".join(str(idx) for idx in slice_indices)
                try:
                    await set_test_group(
                        problem_id,
                        "tests",
                        group_cfg["group"],
                        indices_str,
                        user_id,
                        db,
                    )
                    logger.info(
                        f"[{session_id}] Assigned tests [{indices_str}] to group {group_cfg['group']}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[{session_id}] Failed to assign tests to group {group_cfg['group']}: {e}"
                    )
    except Exception as e:
        logger.warning(f"[{session_id}] _assign_tests_to_groups failed: {e}")


async def _upload_problem_settings(
    problem_id: int,
    user_id: int,
    problem_settings: dict | None,
    db: AsyncSession,
):
    if not problem_settings:
        return
    try:
        await update_info(
            problem_id=problem_id,
            input_file_name=problem_settings.get("input_file", ""),
            output_file_name=problem_settings.get("output_file", ""),
            interactive=problem_settings.get("interactive", False),
            time_limit=problem_settings.get("time_limit", 0),
            memory_limit=problem_settings.get("memory_limit", 0),
            user_id=user_id,
            db=db,
        )
    except Exception as e:
        logger.warning(f"Failed to update problem info: {e}")


async def _upload_tags(
    problem_id: int,
    user_id: int,
    problem_settings: dict | None,
    db: AsyncSession,
):
    if not problem_settings:
        return
    tags = problem_settings.get("tags", [])
    if not tags:
        return
    try:
        await set_tags(problem_id, ",".join(tags), user_id, db)
    except Exception as e:
        logger.warning(f"Failed to upload tags: {e}")


async def _upload_examples(
    problem_id: int,
    user_id: int,
    examples: list | None,
    db: AsyncSession,
):
    if not examples:
        return
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


async def run_upload_pipeline(session_id: str):
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        user_id = res.user_id
        statement = res.statement
        model = res.model
        problem_settings = res.problem_settings or {}
        solution_meta = res.solution_meta or {}
        examples = res.examples or []
        interactive = problem_settings.get("interactive", False)

        progress = {
            "status": "uploading",
            "current_step": "Создание задачи в Polygon...",
            "retries": 0,
            "error": None,
        }
        await _update_session(
            session_id, {"progress": progress, "stage": PipelineStage.UPLOADING}, db
        )

        try:
            # 1. Создаём задачу если ещё нет
            if res.polygon_problem_id:
                problem_id = res.polygon_problem_id
                logger.info(
                    f"[{session_id}] Reusing existing Polygon problem {problem_id}"
                )
            else:
                polygon_name = _make_polygon_name(model, statement, session_id)
                logger.info(f"[{session_id}] Creating Polygon problem '{polygon_name}'")
                problem_id = await create_problem(
                    name=polygon_name, user_id=user_id, db=db
                )
                logger.info(f"[{session_id}] Problem created: polygon_id={problem_id}")
                await _update_session(
                    session_id, {"polygon_problem_id": problem_id}, db
                )

            # 2. Настройки задачи (TL, ML, interactive, input/output files)
            if problem_settings:
                progress["current_step"] = "Настройка параметров задачи..."
                await _update_session(session_id, {"progress": progress}, db)
                await _upload_problem_settings(
                    problem_id, user_id, problem_settings, db
                )

            # 3. Условие
            progress["current_step"] = "Загрузка условия..."
            await _update_session(session_id, {"progress": progress}, db)
            interaction_text = statement.get("interaction", "") if interactive else ""
            await save_statement(
                problem_id=problem_id,
                lang="russian",
                name=statement["name"],
                legend=statement["legend"],
                input_legend=statement["input"],
                output_legend=statement["output"],
                notes=statement.get("notes"),
                tutorial=statement.get("tutorial"),
                scoring=statement.get("scoring", ""),
                interaction=interaction_text,
                user_id=user_id,
                db=db,
            )

            # 4. Примеры-тесты
            if examples:
                progress["current_step"] = "Загрузка примеров..."
                await _update_session(session_id, {"progress": progress}, db)
                await _upload_examples(problem_id, user_id, examples, db)

            # 5. Теги
            if problem_settings.get("tags"):
                progress["current_step"] = "Загрузка тегов..."
                await _update_session(session_id, {"progress": progress}, db)
                await _upload_tags(problem_id, user_id, problem_settings, db)

            # 5.5. Группы тестов и баллы
            scoring_groups = await _setup_groups_and_points(
                session_id,
                problem_id,
                user_id,
                problem_settings,
                (statement or {}).get("scoring"),
                progress,
                db,
            )

            # 6. Технические файлы
            upload_errors = await _upload_steps(
                session_id,
                problem_id,
                user_id,
                statement,
                model,
                progress,
                db,
                solution_meta=solution_meta,
                include_interactor=interactive,
            )

            # Save any per-file errors (marked with ⚠️ in the UI) but keep going
            if upload_errors:
                await _update_session(session_id, {"upload_errors": upload_errors}, db)

            # 7. Коммит
            progress["current_step"] = "Коммит изменений..."
            await _update_session(session_id, {"progress": progress}, db)
            await commit(problem_id, user_id, db, minor_changes=True, message="gpt-generated-task")

            # 8. Сборка пакета
            await _build_and_poll_package(
                session_id,
                problem_id,
                user_id,
                progress,
                db,
                scoring_groups=scoring_groups if scoring_groups else None,
            )

        except Exception as e:
            logger.exception(f"[{session_id}] Upload pipeline failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            progress["traceback"] = traceback.format_exc()
            await _update_session(
                session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
            )


async def retry_upload_after_manual_fix(session_id: str):
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        statement = res.statement
        user_id = res.user_id
        model = res.model
        problem_id = res.polygon_problem_id
        problem_settings = res.problem_settings or {}
        solution_meta = res.solution_meta or {}
        interactive = problem_settings.get("interactive", False)
        scoring_groups = _parse_scoring_groups((statement or {}).get("scoring"))

        if not problem_id:
            logger.error(
                f"[{session_id}] retry_upload called but polygon_problem_id is not set"
            )
            await _update_session(
                session_id,
                {
                    "progress": {
                        "status": "failed",
                        "error": "Polygon problem ID not set",
                    },
                    "stage": PipelineStage.FAILED,
                },
                db,
            )
            return

        progress = {
            "status": "uploading",
            "current_step": "Повторная загрузка исправленных файлов...",
            "retries": 0,
            "error": None,
        }
        await _update_session(
            session_id, {"progress": progress, "stage": PipelineStage.UPLOADING}, db
        )

        try:
            upload_errors = await _upload_steps(
                session_id,
                problem_id,
                user_id,
                statement,
                model,
                progress,
                db,
                solution_meta=solution_meta,
                include_interactor=interactive,
            )

            if upload_errors:
                progress["status"] = "waiting_manual_fix"
                progress["current_step"] = "Ошибки остались после повторной попытки"
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "upload_errors": upload_errors,
                        "stage": PipelineStage.FIXING_ERRORS,
                    },
                    db,
                )
                return

            await _update_session(session_id, {"upload_errors": {}}, db)

            progress["current_step"] = "Коммит изменений..."
            await _update_session(session_id, {"progress": progress}, db)
            await commit(problem_id, user_id, db, minor_changes=True, message="gpt-generated-task")

            await _build_and_poll_package(
                session_id,
                problem_id,
                user_id,
                progress,
                db,
                scoring_groups=scoring_groups if scoring_groups else None,
            )

        except Exception as e:
            logger.exception(f"[{session_id}] Retry pipeline failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            await _update_session(
                session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
            )


async def _build_and_poll_package(
    session_id: str,
    problem_id: int,
    user_id: int,
    progress: Dict,
    db: AsyncSession,
    scoring_groups: list[dict] | None = None,
):
    from api.user.polygon.commit.build_package import \
        build_package as polygon_build_package

    for build_attempt in range(1, MAX_BUILD_RETRIES + 1):
        progress["current_step"] = (
            f"Запуск сборки пакета (попытка {build_attempt}/{MAX_BUILD_RETRIES})..."
            if build_attempt > 1
            else "Запуск сборки пакета..."
        )
        await _update_session(
            session_id,
            {"progress": progress, "stage": PipelineStage.BUILDING_PACKAGE},
            db,
        )

        await polygon_build_package(problem_id=problem_id, user_id=user_id, db=db)

        elapsed = 0
        package_failed = False
        while elapsed < PACKAGE_POLL_TIMEOUT:
            await asyncio.sleep(PACKAGE_POLL_INTERVAL)
            elapsed += PACKAGE_POLL_INTERVAL

            packages = await get_packages(problem_id, user_id, db)
            if not packages:
                continue

            latest = packages[-1]
            state = latest.get("state", "PENDING")
            package_id = latest.get("id")

            progress["current_step"] = f"Сборка пакета: {state}..."
            await _update_session(session_id, {"progress": progress}, db)

            if state == "READY":
                logger.info(
                    f"[{session_id}] Package built: polygon_id={problem_id} package_id={package_id}"
                )

                # Post-build: assign tests to groups if configured
                if scoring_groups:
                    progress["current_step"] = "Назначение тестов группам..."
                    await _update_session(session_id, {"progress": progress}, db)
                    await _assign_tests_to_groups(
                        session_id, problem_id, user_id, scoring_groups, progress, db
                    )
                    # Recommit after group assignment so it takes effect
                    try:
                        progress["current_step"] = (
                            "Финальный коммит после назначения групп..."
                        )
                        await _update_session(session_id, {"progress": progress}, db)
                        await commit(problem_id, user_id, db, minor_changes=True, message="gpt-generated-task")
                    except Exception as e:
                        logger.warning(
                            f"[{session_id}] Re-commit after group assignment failed: {e}"
                        )

                progress["status"] = "done"
                progress["current_step"] = (
                    f"Задача создана! Polygon ID: {problem_id}, Package: {package_id}"
                )
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "stage": PipelineStage.DONE,
                        "package_id": package_id,
                    },
                    db,
                )
                await _append_chat_log(
                    session_id,
                    [
                        {
                            "id": str(_uuid.uuid4()),
                            "role": "system",
                            "content": (
                                f"✅ Задача успешно создана на Polygon. ID задачи: {problem_id}. "
                                f"Найдите её на polygon.codeforces.com в списке своих задач."
                            ),
                            "timestamp": _now_iso(),
                        },
                        {
                            "id": str(_uuid.uuid4()),
                            "role": "system",
                            "content": (
                                "⚠️ Не рекомендуется изменять файлы напрямую на Polygon — "
                                "такие правки не попадут в контекст ИИ и будут перезаписаны при следующей загрузке."
                            ),
                            "timestamp": _now_iso(),
                        },
                    ],
                    db,
                )
                return

            elif state == "FAILED":
                error_comment = latest.get(
                    "comment", "Неизвестная ошибка сборки пакета"
                )
                logger.error(
                    f"[{session_id}] Package build attempt {build_attempt} failed: {error_comment}"
                )
                package_failed = True
                break

        if not package_failed:
            # Timed out waiting for this attempt
            logger.error(
                f"[{session_id}] Package build attempt {build_attempt} timed out"
            )

        if build_attempt < MAX_BUILD_RETRIES:
            logger.info(
                f"[{session_id}] Retrying package build (attempt {build_attempt + 1})..."
            )
            progress["current_step"] = (
                f"Повторная попытка сборки ({build_attempt + 1}/{MAX_BUILD_RETRIES})..."
            )
            await _update_session(session_id, {"progress": progress}, db)
            try:
                await commit(problem_id, user_id, db, minor_changes=True, message="gpt-generated-task")
            except Exception as e:
                logger.warning(f"[{session_id}] Re-commit before retry failed: {e}")
            await asyncio.sleep(5)
        else:
            # All retries exhausted
            packages = await get_packages(problem_id, user_id, db)
            latest = packages[-1] if packages else {}
            error_comment = latest.get("comment", "Неизвестная ошибка сборки пакета")
            progress["status"] = "waiting_manual_fix"
            progress["current_step"] = "Ошибка сборки пакета (все попытки исчерпаны)"
            progress["error"] = error_comment
            await _update_session(
                session_id,
                {
                    "progress": progress,
                    "stage": PipelineStage.FIXING_ERRORS,
                    "upload_errors": {
                        "package": {
                            "error": error_comment,
                            "needs_manual_fix": True,
                        }
                    },
                },
                db,
            )
            return

    logger.error(
        f"[{session_id}] Package build timed out after {PACKAGE_POLL_TIMEOUT}s"
    )
    progress["status"] = "failed"
    progress["current_step"] = "Таймаут сборки пакета"
    await _update_session(
        session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
    )
