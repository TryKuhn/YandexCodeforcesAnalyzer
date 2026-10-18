"""Problem statements and their resources."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call


async def get_statements(
    problem_id: int, user_id: int, db: AsyncSession
) -> dict[str, dict[str, Any]]:
    """``problem.statements`` -> ``{language: Statement}``."""
    result = await call("problem.statements", user_id, db, problemId=problem_id)
    return result if isinstance(result, dict) else {}


async def render_statements(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    include_content: bool | None = None,
) -> dict[str, Any]:
    """``problem.renderStatements`` -> ``RenderStatements`` (HTML/PDF statements, tutorials)."""
    return await call(
        "problem.renderStatements", user_id, db,
        problemId=problem_id, includeContent=include_content,
    )


async def save_statement(
    problem_id: int,
    lang: str,
    user_id: int,
    db: AsyncSession,
    *,
    encoding: str | None = None,
    name: str | None = None,
    legend: str | None = None,
    input: str | None = None,
    output: str | None = None,
    scoring: str | None = None,
    interaction: str | None = None,
    notes: str | None = None,
    tutorial: str | None = None,
    show_in_review: bool | None = None,
    show_cautions_and_grammatical_fixes: bool | None = None,
) -> None:
    """``problem.saveStatement`` -- only the given (non-``None``) fields are sent.

    An empty string is sent and clears the section.
    """
    method = "problem.saveStatement"
    if name is not None and any(ch in name for ch in "\r\n  "):
        raise PolygonParamError("name: название должно быть в одну строку", method=method)
    await call(
        method, user_id, db,
        problemId=problem_id,
        lang=lang,
        encoding=encoding,
        name=name,
        legend=legend,
        input=input,
        output=output,
        scoring=scoring,
        interaction=interaction,
        notes=notes,
        tutorial=tutorial,
        showInReview=show_in_review,
        showCautionsAndGrammaticalFixes=show_cautions_and_grammatical_fixes,
    )


async def get_statement_resources(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.statementResources`` -> ``File[]``."""
    result = await call("problem.statementResources", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def view_statement_resource(
    problem_id: int, name: str, user_id: int, db: AsyncSession
) -> bytes:
    """``problem.viewStatementResource`` -> raw file bytes."""
    return await call(
        "problem.viewStatementResource", user_id, db,
        kind="bytes", problemId=problem_id, name=name,
    )


async def save_statement_resource(
    problem_id: int,
    name: str,
    file: bytes | str,
    user_id: int,
    db: AsyncSession,
    *,
    check_existing: bool | None = None,
) -> None:
    """``problem.saveStatementResource`` (images go as a multipart field)."""
    await call(
        "problem.saveStatementResource", user_id, db,
        problemId=problem_id, name=name, file=file, checkExisting=check_existing,
    )
