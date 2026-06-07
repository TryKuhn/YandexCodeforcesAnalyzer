"""Tool-calling AI agent for Polygon problems.

The agent has read-only tools to inspect the problem (statement, info,
tests, files, solutions) and uses them to answer user questions.
"""
import base64
import json
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.user.gpt import gpt_router
from api.user.polygon.client import get_user, polygon_call
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.session import TaskSession
from models.task.statement import PolygonStatement
from models.task.test import PolygonTest
from models.task.test_group import PolygonTestGroup
from settings import settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6

# ── Tool definitions (OpenAI tool-calling format) ─────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_statement",
            "description": "Returns the problem statement in the given language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lang": {
                        "type": "string",
                        "description": "Language code: 'russian' or 'english'",
                        "enum": ["russian", "english"],
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_problem_info",
            "description": "Returns problem metadata: time limit, memory limit, interactive flag, I/O files.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tests",
            "description": "Returns a list of tests (up to `limit`). For manual tests includes input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of tests to return (default 10)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file",
            "description": "Returns the content of a source/resource/aux file by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "description": "File type: 'source', 'resource', or 'aux'",
                        "enum": ["source", "resource", "aux"],
                    },
                    "name": {
                        "type": "string",
                        "description": "File name (e.g. 'checker.cpp')",
                    },
                },
                "required": ["file_type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solutions",
            "description": "Returns a list of solutions with their names and tags.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solution_content",
            "description": "Returns the source code of a solution by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Solution file name (e.g. 'sol.cpp')",
                    }
                },
                "required": ["name"],
            },
        },
    },
]

# ── Tool execution ────────────────────────────────────────────────────────────


async def _execute_tool(
    name: str, args: dict, polygon_id: int, db: AsyncSession, user_id: int
) -> str:
    try:
        if name == "get_statement":
            lang = args.get("lang", "russian")
            problem_res = await db.execute(
                select(PolygonProblem).where(
                    PolygonProblem.user_id == user_id,
                    PolygonProblem.polygon_id == polygon_id,
                )
            )
            problem = problem_res.scalars().first()
            if not problem:
                return "Problem not found in cache."
            stmt_res = await db.execute(
                select(PolygonStatement).where(
                    PolygonStatement.problem_id == problem.id,
                    PolygonStatement.lang == lang,
                )
            )
            stmt = stmt_res.scalars().first()
            if not stmt:
                return f"Statement in '{lang}' not found. Try syncing first."
            return json.dumps(
                {
                    "name": stmt.name,
                    "legend": stmt.legend,
                    "input": stmt.input,
                    "output": stmt.output,
                    "scoring": stmt.scoring,
                    "interaction": stmt.interaction,
                    "notes": stmt.notes,
                    "tutorial": stmt.tutorial,
                },
                ensure_ascii=False,
            )

        elif name == "get_problem_info":
            problem_res = await db.execute(
                select(PolygonProblem).where(
                    PolygonProblem.user_id == user_id,
                    PolygonProblem.polygon_id == polygon_id,
                )
            )
            problem = problem_res.scalars().first()
            if not problem:
                return "Problem not found in cache."
            return json.dumps(
                {
                    "inputFile": problem.input_file or "stdin",
                    "outputFile": problem.output_file or "stdout",
                    "interactive": problem.interactive,
                    "timeLimit": problem.time_limit,
                    "memoryLimit": problem.memory_limit,
                    "wellFormed": problem.well_formed,
                },
                ensure_ascii=False,
            )

        elif name == "get_tests":
            limit = int(args.get("limit", 10))
            problem_res = await db.execute(
                select(PolygonProblem).where(
                    PolygonProblem.user_id == user_id,
                    PolygonProblem.polygon_id == polygon_id,
                )
            )
            problem = problem_res.scalars().first()
            if not problem:
                return "Problem not found in cache."
            tests_res = await db.execute(
                select(PolygonTest)
                .where(PolygonTest.problem_id == problem.id)
                .limit(limit)
            )
            tests = tests_res.scalars().all()
            if not tests:
                return "No tests in cache. Sync to load tests."
            result = []
            for t in tests:
                entry: dict[str, Any] = {
                    "index": t.index,
                    "group": t.group,
                    "points": t.points,
                    "useInStatements": t.use_in_statements,
                }
                if t.input_b64:
                    try:
                        entry["input"] = base64.b64decode(t.input_b64).decode(
                            "utf-8", errors="replace"
                        )[:500]
                    except Exception:
                        entry["input"] = "(binary)"
                result.append(entry)
            return json.dumps(result, ensure_ascii=False)

        elif name == "get_file":
            file_type = args.get("file_type", "source")
            fname = args.get("name", "")
            user = await get_user(user_id, db)
            content = await polygon_call(
                "problem.viewFile",
                {"problemId": str(polygon_id), "type": file_type, "name": fname},
                user,
            )
            text = content.get("message", "") if isinstance(content, dict) else str(content)
            return text[:8000]

        elif name == "get_solutions":
            user = await get_user(user_id, db)
            sols = await polygon_call(
                "problem.solutions", {"problemId": str(polygon_id)}, user
            )
            if isinstance(sols, list):
                return json.dumps(
                    [{"name": s.get("name"), "tag": s.get("tag")} for s in sols],
                    ensure_ascii=False,
                )
            return json.dumps(sols, ensure_ascii=False)

        elif name == "get_solution_content":
            fname = args.get("name", "")
            user = await get_user(user_id, db)
            content = await polygon_call(
                "problem.viewSolution",
                {"problemId": str(polygon_id), "name": fname},
                user,
            )
            text = content.get("message", "") if isinstance(content, dict) else str(content)
            return text[:8000]

    except Exception as exc:
        logger.warning(f"Tool {name} error: {exc}")
        return f"Tool error: {exc}"

    return "Unknown tool"


# ── Request/response schema ───────────────────────────────────────────────────


class PolygonAgentChatRequest(BaseModel):
    session_id: str
    message: str
    model: str = "anthropic/claude-sonnet-4.6"
    attachments: list[dict] = []  # [{"type": "file"|"test", "label": str, "content": str}]


# ── Endpoint ──────────────────────────────────────────────────────────────────


@gpt_router.post("/polygon-chat")
async def polygon_agent_chat(
    request: PolygonAgentChatRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_res = await db.execute(
        select(TaskSession).where(
            TaskSession.id == request.session_id,
            TaskSession.user_id == user_id,
        )
    )
    session = session_res.scalars().first()
    if not session or not session.polygon_problem_id:
        raise HTTPException(status_code=404, detail="Session not found")

    polygon_id = session.polygon_problem_id

    # Build conversation from stored history
    history: list[dict] = list(session.history or [])

    # Inject attached context into user message
    user_content = request.message
    if request.attachments:
        parts = [user_content]
        for att in request.attachments:
            parts.append(
                f"\n\n--- Прикреплённый контекст: {att.get('label', '')} ---\n{att.get('content', '')}"
            )
        user_content = "".join(parts)

    history.append({"role": "user", "content": user_content})

    # Tool-calling loop
    base_url = settings.OPENAI_HOST.rstrip("/")
    url = (
        f"{base_url}/chat/completions"
        if not base_url.endswith("/chat/completions")
        else base_url
    )
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    system_msg = {
        "role": "system",
        "content": (
            "Ты — ИИ-ассистент для разработки задач в Polygon (polygon.codeforces.com). "
            "У тебя есть инструменты для чтения данных задачи. "
            "Используй их, чтобы давать точные ответы. "
            "Отвечай на русском языке, если пользователь не попросил иначе."
        ),
    }

    messages = [system_msg] + history
    final_response = ""

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=500, detail=f"AI error: {resp.text[:300]}"
                )
            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]

            if choice.get("finish_reason") == "tool_calls" or msg.get("tool_calls"):
                messages.append(msg)
                for tc in msg.get("tool_calls", []):
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}
                    tool_result = await _execute_tool(
                        tool_name, tool_args, polygon_id, db, user_id
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result,
                        }
                    )
            else:
                final_response = msg.get("content") or ""
                break

    if not final_response:
        final_response = "Не удалось получить ответ от агента."

    # Store conversation (without system message, without tool messages)
    new_history = [m for m in messages[1:] if m.get("role") in ("user", "assistant")]
    # Add final assistant response if not already there
    if new_history and new_history[-1].get("role") != "assistant":
        new_history.append({"role": "assistant", "content": final_response})

    session.history = new_history
    flag_modified(session, "history")
    session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update chat_log for UI display (id + timestamp)
    chat_log = list(session.chat_log or [])
    ts = datetime.now(timezone.utc).isoformat()
    chat_log.append({
        "id": str(_uuid.uuid4()),
        "role": "user",
        "content": request.message,
        "timestamp": ts,
    })
    chat_log.append({
        "id": str(_uuid.uuid4()),
        "role": "assistant",
        "content": final_response,
        "timestamp": ts,
    })
    session.chat_log = chat_log
    flag_modified(session, "chat_log")

    await db.commit()
    return {"response": final_response}
