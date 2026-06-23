"""Save a problem statement for a given language via the Polygon API."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_statement(
    problem_id: int,
    lang: str,
    name: str,
    legend: str,
    input_legend: str,
    output_legend: str,
    user_id: int,
    db: AsyncSession,
    scoring: Optional[str] = None,
    interaction: Optional[str] = None,
    notes: Optional[str] = None,
    tutorial: Optional[str] = None,
    encoding: str = "utf-8",
):
    """Save a problem statement for one language via Polygon's
    ``problem.saveStatement``.

    Optional fields (``scoring``, ``interaction``, ``notes``, ``tutorial``)
    are only sent to Polygon when truthy."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "lang": lang,
        "encoding": encoding,
        "name": name,
        "legend": legend,
        "input": input_legend,
        "output": output_legend,
    }
    if scoring:
        params["scoring"] = scoring
    if interaction:
        params["interaction"] = interaction
    if notes:
        params["notes"] = notes
    if tutorial:
        params["tutorial"] = tutorial

    return await polygon_call("problem.saveStatement", params, user)
