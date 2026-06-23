"""Import an existing Polygon problem into a new AI session.

Reads statement / info / tags / files / solutions / script / sample tests from
Polygon and materialises them as a TaskSession plus TaskGeneratedFile rows. All
Polygon reads go through the polygon wrappers; this module only orchestrates and
maps them onto our session model.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.sessions import new_id, now_utc
from api.user.polygon.files.get.files import get_files
from api.user.polygon.files.get.view_file import view_file
from api.user.polygon.files.script.get.script import get_script
from api.user.polygon.files.solution.get.solutions import get_solutions
from api.user.polygon.files.solution.get.view_solution import view_solution
from api.user.polygon.files.test.get.test_input import get_test_input
from api.user.polygon.files.test.get.tests import get_tests
from api.user.polygon.problem.get.info import get_problem_info
from api.user.polygon.problem.get.tags import view_tags
from api.user.polygon.statement.get.setatement import get_statements
from models.task.session import PipelineStage, ProblemType, TaskSession

logger = logging.getLogger(__name__)

KNOWN_SOURCE_FILES = {
    "validator.cpp": "validator",
    "checker.cpp": "checker",
    "generator.cpp": "generator",
    "interactor.cpp": "interactor",
}

_TAG_TO_TYPE = {
    "MA": "solution_cpp",
    "WA": "wa_sol",
    "TL": "tl_sol",
    "ML": "ml_sol",
    "RE": "re_sol",
}


def _extract_statement(raw) -> dict:
    """Pick the russian (else english, else first) statement and normalise its fields."""
    data: dict = (
        raw.get("russian") or raw.get("english") or next(iter(raw.values()), {})
        if isinstance(raw, dict) else {}
    )
    return {
        "name": data.get("name", ""),
        "legend": data.get("legend", ""),
        "input": data.get("input", ""),
        "output": data.get("output", ""),
        "notes": data.get("notes") or "",
        "tutorial": data.get("tutorial") or "",
    }


async def _load_source_files(db, session_id, problem_id, user_id, tech_data) -> None:
    """Pull known Polygon source files into ``tech_data`` and persist them."""
    try:
        files_info = await get_files(problem_id, user_id, db)
        for f in files_info.get("sourceFiles", []) or []:
            name = f.get("name", "")
            if name not in KNOWN_SOURCE_FILES:
                continue
            try:
                content = await view_file(problem_id, "source", name, user_id, db)
                file_type = KNOWN_SOURCE_FILES[name]
                tech_data[file_type] = content
                await upsert_ai_file(db, session_id, file_type, content, uploaded=True)
            except Exception as e:
                logger.warning(f"Failed to load file {name}: {e}")
    except Exception as e:
        logger.warning(f"Failed to load problem files: {e}")


async def _load_solutions(db, session, problem_id, user_id, tech_data) -> None:
    """Pull Polygon solutions into ``tech_data``, mapping tags to file types.

    Unknown tags get a ``sol_custom_<hex>`` type recorded in ``solution_meta``.
    """
    try:
        solutions = await get_solutions(problem_id, user_id, db)
        solution_meta = {}
        for sol in solutions:
            name = sol.get("name", "")
            tag = (sol.get("tag", "OK") or "OK").upper()
            try:
                content = await view_solution(problem_id, name, user_id, db)
                file_type = _TAG_TO_TYPE.get(tag)
                if file_type is None:
                    file_type = f"sol_custom_{uuid.uuid4().hex[:8]}"
                    solution_meta[file_type] = {"tag": tag, "name": name}
                tech_data[file_type] = content
                await upsert_ai_file(db, session.id, file_type, content, uploaded=True)
            except Exception as e:
                logger.warning(f"Failed to load solution {name}: {e}")
        if solution_meta:
            session.solution_meta = solution_meta
    except Exception as e:
        logger.warning(f"Failed to load solutions: {e}")


async def import_full(db: AsyncSession, user_id: int, problem_id: int,
                      model: str, load_files: bool) -> dict:
    """Build and persist a session from a Polygon problem. Returns the response."""
    raw_stmts = await get_statements(problem_id, user_id, db)
    statement = _extract_statement(raw_stmts)

    try:
        info = await get_problem_info(problem_id, user_id, db)
    except Exception:
        info = {}

    is_interactive = bool(info.get("interactive", False))
    problem_settings: dict = {
        "input_file": info.get("inputFile", "stdin") or "stdin",
        "output_file": info.get("outputFile", "stdout") or "stdout",
        "interactive": is_interactive,
        "time_limit": info.get("timeLimit", 2000) or 2000,
        "memory_limit": info.get("memoryLimit", 256) or 256,
        "tags": [],
        "enable_groups": False,
        "enable_points": False,
    }

    try:
        problem_settings["tags"] = await view_tags(problem_id, user_id, db)
    except Exception:
        pass

    ts = now_utc()
    session = TaskSession(
        id=new_id(),
        user_id=user_id,
        model=model,
        system_prompt="",
        statement=statement,
        history=[],
        problem_type=(ProblemType.INTERACTIVE if is_interactive
                      else ProblemType.REGULAR),
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        polygon_problem_id=problem_id,
        problem_settings=problem_settings,
        solution_meta={},
        examples=[],
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.flush()

    tech_data: dict = {}
    if load_files:
        await _load_source_files(db, session.id, problem_id, user_id, tech_data)
        await _load_solutions(db, session, problem_id, user_id, tech_data)

        try:
            script = await get_script(problem_id, "tests", user_id, db)
            if script:
                tech_data["script"] = script
                await upsert_ai_file(db, session.id, "script", script, uploaded=True)
        except Exception:
            pass

        try:
            tests = await get_tests(problem_id, "tests", user_id, db)
            examples = []
            for t in tests:
                if t.get("useInStatements"):
                    idx = t.get("index", 0)
                    try:
                        inp = await get_test_input(problem_id, "tests", idx, user_id, db)
                        examples.append({"index": idx, "input": inp, "output": ""})
                    except Exception:
                        pass
            if examples:
                session.examples = examples
        except Exception:
            pass

    await db.commit()

    return {
        "session_id": session.id,
        "statement": statement,
        "stage": PipelineStage.STATEMENT,
        "problem_type": session.problem_type,
        "polygon_problem_id": problem_id,
        "problem_settings": problem_settings,
        "technical_data": tech_data,
        "examples": session.examples or [],
    }
