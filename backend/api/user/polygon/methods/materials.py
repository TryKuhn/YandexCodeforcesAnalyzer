"""Problem materials (problem.materials / problem.setMaterial)."""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call, choice
from api.user.polygon.constants import (MATERIAL_ITEM_TYPES,
                                        MATERIAL_PUBLISH_STRATEGIES)

_MAX_ITEMS_JSON = 262144


async def get_materials(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.materials`` -> ``Material[]``."""
    result = await call("problem.materials", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def save_material(
    problem_id: int,
    name: str,
    publish_strategy: str,
    items: list[dict[str, Any]],
    user_id: int,
    db: AsyncSession,
    *,
    original_name: str | None = None,
) -> None:
    """``problem.setMaterial`` -- create/update (rename via ``original_name``).

    Changes go to the working copy and need a separate commit.
    """
    method = "problem.setMaterial"
    if not 1 <= len(name) <= 40:
        raise PolygonParamError("name: от 1 до 40 символов", method=method)
    if not items:
        raise PolygonParamError("items: нужен хотя бы один элемент", method=method)
    items = [
        {**item, "type": choice(item.get("type"), MATERIAL_ITEM_TYPES, "items[].type",
                                method=method)}
        for item in items
    ]
    items_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    if len(items_json) > _MAX_ITEMS_JSON:
        raise PolygonParamError("items: JSON длиннее 262144 символов", method=method)
    await call(
        method, user_id, db,
        problemId=problem_id,
        name=name,
        originalName=original_name,
        publishStrategy=choice(
            publish_strategy, MATERIAL_PUBLISH_STRATEGIES, "publishStrategy", method=method
        ),
        items=items_json,
    )


async def remove_material(problem_id: int, name: str, user_id: int, db: AsyncSession) -> None:
    """``problem.setMaterial`` with ``remove=true``."""
    await call("problem.setMaterial", user_id, db, problemId=problem_id, name=name, remove=True)
