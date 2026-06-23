"""Read-only tool-calling agent over a Polygon problem (cached data + live reads).

Used by the /polygon-chat endpoint to answer questions about a problem that is
already on Polygon. Has inspection tools only — it never modifies the problem.
Moved out of the old top-level polygon_agent.py module.
"""
import base64
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.user.gpt.services.sessions import chat_message, now_utc
from api.user.polygon.client import get_user, polygon_call
from models.task.problem import PolygonProblem
from models.task.session import TaskSession
from models.task.statement import PolygonStatement
from models.task.test import PolygonTest
from settings import settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6

TOOLS = [
    {"type": "function", "function": {
        "name": "get_statement",
        "description": "Returns the problem statement in the given language.",
        "parameters": {"type": "object", "properties": {
            "lang": {"type": "string", "enum": ["russian", "english"]}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_problem_info",
        "description": "Returns problem metadata: time/memory limit, interactive flag, I/O files.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_tests",
        "description": "Returns a list of tests (up to `limit`). For manual tests includes input.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_file",
        "description": "Returns the content of a source/resource/aux file by name.",
        "parameters": {"type": "object", "properties": {
            "file_type": {"type": "string", "enum": ["source", "resource", "aux"]},
            "name": {"type": "string"}}, "required": ["file_type", "name"]}}},
    {"type": "function", "function": {
        "name": "get_solutions",
        "description": "Returns a list of solutions with their names and tags.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_solution_content",
        "description": "Returns the source code of a solution by name.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
]


async def _execute_tool(name: str, args: dict, polygon_id: int,
                        db: AsyncSession, user_id: int) -> str:
    """Run one inspection tool by name and return its result as a string.

    Statement/info/tests are served from the cached DB rows; file/solution
    reads hit Polygon live. Returns an error string on any failure.
    """
    try:
        if name in ("get_statement", "get_problem_info", "get_tests"):
            problem_res = await db.execute(select(PolygonProblem).where(
                PolygonProblem.user_id == user_id,
                PolygonProblem.polygon_id == polygon_id))
            problem = problem_res.scalars().first()
            if not problem:
                return "Problem not found in cache."

            if name == "get_statement":
                lang = args.get("lang", "russian")
                stmt_res = await db.execute(select(PolygonStatement).where(
                    PolygonStatement.problem_id == problem.id,
                    PolygonStatement.lang == lang))
                stmt = stmt_res.scalars().first()
                if not stmt:
                    return f"Statement in '{lang}' not found. Try syncing first."
                return json.dumps({
                    "name": stmt.name, "legend": stmt.legend, "input": stmt.input,
                    "output": stmt.output, "scoring": stmt.scoring,
                    "interaction": stmt.interaction, "notes": stmt.notes,
                    "tutorial": stmt.tutorial}, ensure_ascii=False)

            if name == "get_problem_info":
                return json.dumps({
                    "inputFile": problem.input_file or "stdin",
                    "outputFile": problem.output_file or "stdout",
                    "interactive": problem.interactive,
                    "timeLimit": problem.time_limit,
                    "memoryLimit": problem.memory_limit,
                    "wellFormed": problem.well_formed}, ensure_ascii=False)

            limit = int(args.get("limit", 10))
            tests_res = await db.execute(select(PolygonTest)
                                         .where(PolygonTest.problem_id == problem.id)
                                         .limit(limit))
            tests = tests_res.scalars().all()
            if not tests:
                return "No tests in cache. Sync to load tests."
            result = []
            for t in tests:
                entry: dict[str, Any] = {"index": t.index, "group": t.group,
                                         "points": t.points,
                                         "useInStatements": t.use_in_statements}
                if t.input_b64:
                    try:
                        entry["input"] = base64.b64decode(t.input_b64).decode(
                            "utf-8", errors="replace")[:500]
                    except Exception:
                        entry["input"] = "(binary)"
                result.append(entry)
            return json.dumps(result, ensure_ascii=False)

        if name == "get_file":
            user = await get_user(user_id, db)
            content = await polygon_call("problem.viewFile", {
                "problemId": str(polygon_id), "type": args.get("file_type", "source"),
                "name": args.get("name", "")}, user)
            text = content.get("message", "") if isinstance(content, dict) else str(content)
            return text[:8000]

        if name == "get_solutions":
            user = await get_user(user_id, db)
            sols = await polygon_call("problem.solutions", {"problemId": str(polygon_id)}, user)
            if isinstance(sols, list):
                return json.dumps([{"name": s.get("name"), "tag": s.get("tag")} for s in sols],
                                  ensure_ascii=False)
            return json.dumps(sols, ensure_ascii=False)

        if name == "get_solution_content":
            user = await get_user(user_id, db)
            content = await polygon_call("problem.viewSolution", {
                "problemId": str(polygon_id), "name": args.get("name", "")}, user)
            text = content.get("message", "") if isinstance(content, dict) else str(content)
            return text[:8000]

    except Exception as exc:
        logger.warning(f"Tool {name} error: {exc}")
        return f"Tool error: {exc}"
    return "Unknown tool"


_SYSTEM = {
    "role": "system",
    "content": (
        "Ты — ИИ-ассистент для разработки задач в Polygon (polygon.codeforces.com). "
        "У тебя есть инструменты для чтения данных задачи. Используй их, чтобы давать "
        "точные ответы. Отвечай на русском языке, если пользователь не попросил иначе."
    ),
}


async def run_agent(db: AsyncSession, session: TaskSession, user_id: int,
                    message: str, model: str, attachments: list[dict]) -> str:
    """Run the tool loop, persist history + chat_log, return the final answer."""
    polygon_id = session.polygon_problem_id
    history: list[dict] = list(session.history or [])

    user_content = message
    if attachments:
        parts = [user_content]
        for att in attachments:
            parts.append(f"\n\n--- Прикреплённый контекст: {att.get('label', '')} ---\n"
                         f"{att.get('content', '')}")
        user_content = "".join(parts)
    history.append({"role": "user", "content": user_content})

    base_url = settings.OPENAI_HOST.rstrip("/")
    url = (f"{base_url}/chat/completions"
           if not base_url.endswith("/chat/completions") else base_url)
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}",
               "Content-Type": "application/json"}

    messages = [_SYSTEM] + history
    final_response = ""

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(MAX_TOOL_ROUNDS):
            payload = {"model": model, "messages": messages,
                       "tools": TOOLS, "tool_choice": "auto"}
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail=f"AI error: {resp.text[:300]}")
            choice = resp.json()["choices"][0]
            msg = choice["message"]

            if choice.get("finish_reason") == "tool_calls" or msg.get("tool_calls"):
                messages.append(msg)
                for tc in msg.get("tool_calls", []):
                    try:
                        tool_args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}
                    tool_result = await _execute_tool(
                        tc["function"]["name"], tool_args, polygon_id, db, user_id)
                    messages.append({"role": "tool", "tool_call_id": tc["id"],
                                     "content": tool_result})
            else:
                final_response = msg.get("content") or ""
                break

    if not final_response:
        final_response = "Не удалось получить ответ от агента."

    new_history = [m for m in messages[1:] if m.get("role") in ("user", "assistant")]
    if new_history and new_history[-1].get("role") != "assistant":
        new_history.append({"role": "assistant", "content": final_response})
    session.history = new_history
    flag_modified(session, "history")

    chat_log = list(session.chat_log or [])
    chat_log.append(chat_message("user", message))
    chat_log.append(chat_message("assistant", final_response))
    session.chat_log = chat_log
    flag_modified(session, "chat_log")
    session.updated_at = now_utc()
    await db.commit()

    return final_response
