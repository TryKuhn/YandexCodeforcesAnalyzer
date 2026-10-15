"""Client for the backend's Polygon routes (``/api/polygon/...``).

The service never signs Polygon requests itself: the backend owns the user's
Polygon credentials and the signing/retry logic. Every call is made as the user
with a short-lived token minted by :func:`authoring.auth.mint_user_token`.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from authoring.auth import mint_user_token
from authoring.settings import settings

logger = logging.getLogger(__name__)

TESTSET = "tests"


class PolygonError(Exception):
    """A failed backend/Polygon call; ``message`` is the backend's ``detail``."""

    def __init__(self, message: str, *, status: int | None = None, path: str = ""):
        super().__init__(message)
        self.message = message
        self.status = status
        self.path = path

    def __str__(self) -> str:
        return self.message


class PolygonClient:
    """Calls ``/api/polygon/problems/{id}/...`` on behalf of one user."""

    def __init__(
        self,
        user_id: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.base_url = (base_url or settings.BACKEND_API_URL).rstrip("/")
        self._transport = transport

    # ------------------------------------------------------------------ core
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        raw: bool = False,
    ) -> Any:
        headers = {"Authorization": f"Bearer {mint_user_token(self.user_id)}"}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.BACKEND_TIMEOUT_SECONDS,
            transport=self._transport,
        ) as http:
            try:
                response = await http.request(method, path, params=params, json=json, headers=headers)
            except httpx.HTTPError as e:
                raise PolygonError(f"backend недоступен: {e!r}", path=path) from e
        if response.status_code >= 400:
            detail: Any = response.text
            try:
                detail = response.json().get("detail", detail)
            except ValueError:
                pass
            raise PolygonError(str(detail)[:2000], status=response.status_code, path=path)
        if raw:
            return response.content
        if not response.content:
            return None
        return response.json()

    def _p(self, problem_id: int, suffix: str = "") -> str:
        return f"/polygon/problems/{problem_id}{suffix}"

    # -------------------------------------------------------------- problems
    async def create_problem(self, name: str) -> int:
        data = await self._request("POST", "/polygon/problems/", json={"name": name})
        return int(data["polygon_id"])

    async def problem(self, problem_id: int) -> dict:
        return await self._request("GET", self._p(problem_id))

    async def info(self, problem_id: int) -> dict:
        return await self._request("GET", self._p(problem_id, "/info"), params={"refresh": "true"})

    async def update_info(self, problem_id: int, **fields: Any) -> None:
        body = {k: v for k, v in fields.items() if v is not None}
        if body:
            await self._request("PATCH", self._p(problem_id, "/info"), json=body)

    async def statements(self, problem_id: int) -> dict[str, dict]:
        data = await self._request(
            "GET", self._p(problem_id, "/statement"), params={"refresh": "true"}
        )
        return data or {}

    async def save_statement(self, problem_id: int, lang: str, fields: dict) -> None:
        body = {"lang": lang, **{k: v for k, v in fields.items() if v is not None}}
        body.setdefault("name", "")
        await self._request("PATCH", self._p(problem_id, "/statement"), json=body)

    async def tags(self, problem_id: int) -> list[str]:
        data = await self._request("GET", self._p(problem_id, "/tags"))
        return list((data or {}).get("tags") or [])

    async def save_tags(self, problem_id: int, tags: list[str]) -> None:
        await self._request("PATCH", self._p(problem_id, "/tags"), json={"tags": tags})

    # ------------------------------------------------------------------ files
    async def files(self, problem_id: int) -> dict:
        """``{resourceFiles, sourceFiles, auxFiles, solutions}``."""
        return await self._request("GET", self._p(problem_id, "/files"))

    async def view_file(self, problem_id: int, file_type: str, name: str) -> str:
        data = await self._request(
            "GET", self._p(problem_id, "/files/content"), params={"type": file_type, "name": name}
        )
        return data.get("content", "")

    async def save_file(self, problem_id: int, file_type: str, name: str, content: str, **extra: Any) -> None:
        body = {"type": file_type, "name": name, "content": content, **extra}
        await self._request("POST", self._p(problem_id, "/files"), json=body)

    async def view_solution(self, problem_id: int, name: str) -> str:
        data = await self._request("GET", self._p(problem_id, f"/solutions/{quote(name, safe='')}/content"))
        return data.get("content", "")

    async def save_solution(self, problem_id: int, name: str, content: str, tag: str | None) -> None:
        await self._request(
            "POST", self._p(problem_id, "/solutions"), json={"name": name, "content": content, "tag": tag}
        )

    async def checker(self, problem_id: int) -> str:
        return (await self._request("GET", self._p(problem_id, "/checker")) or {}).get("checker") or ""

    async def set_checker(self, problem_id: int, name: str, content: str | None = None) -> None:
        """Upload + set a checker; with no ``content`` set an existing/standard one."""
        await self._request(
            "POST", self._p(problem_id, "/checker"), json={"name": name, "content": content}
        )

    async def validator(self, problem_id: int) -> str:
        return (await self._request("GET", self._p(problem_id, "/validator")) or {}).get("validator") or ""

    async def set_validator(self, problem_id: int, name: str, content: str) -> None:
        await self._request("POST", self._p(problem_id, "/validator"), json={"name": name, "content": content})

    async def interactor(self, problem_id: int) -> str:
        return (await self._request("GET", self._p(problem_id, "/interactor")) or {}).get("interactor") or ""

    async def set_interactor(self, problem_id: int, name: str, content: str) -> None:
        await self._request("POST", self._p(problem_id, "/interactor"), json={"name": name, "content": content})

    # ---------------------------------------------------------- tests/script
    async def script(self, problem_id: int, testset: str = TESTSET) -> str:
        data = await self._request("GET", self._p(problem_id, f"/script/{testset}"))
        return (data or {}).get("content") or ""

    async def save_script(self, problem_id: int, source: str, testset: str = TESTSET) -> None:
        await self._request("POST", self._p(problem_id, f"/script/{testset}"), json={"source": source})

    async def clear_script(self, problem_id: int, testset: str = TESTSET) -> None:
        await self._request("DELETE", self._p(problem_id, f"/script/{testset}"))

    async def tests(self, problem_id: int, testset: str = TESTSET) -> list[dict]:
        data = await self._request(
            "GET", self._p(problem_id, f"/tests/{testset}"), params={"no_inputs": "true"}
        )
        return list(data or [])

    async def save_test(self, problem_id: int, index: int, testset: str = TESTSET, **fields: Any) -> None:
        body = {"test_index": index, **{k: v for k, v in fields.items() if v is not None}}
        await self._request("POST", self._p(problem_id, f"/tests/{testset}"), json=body)

    async def delete_tests(self, problem_id: int, indices: list[int], testset: str = TESTSET) -> None:
        await self._request(
            "POST", self._p(problem_id, f"/tests/{testset}/delete"), json={"test_indices": indices}
        )

    async def set_test_group(
        self, problem_id: int, group: str, indices: list[int], testset: str = TESTSET
    ) -> None:
        await self._request(
            "POST",
            self._p(problem_id, f"/tests/{testset}/group"),
            json={"test_indices": indices, "test_group": group},
        )

    async def test_input(self, problem_id: int, index: int, testset: str = TESTSET) -> str:
        data = await self._request("GET", self._p(problem_id, f"/tests/{testset}/{index}/input"))
        return (data or {}).get("content") or ""

    # ------------------------------------------------------- groups/points
    async def enable_groups(self, problem_id: int, enable: bool, testset: str = TESTSET) -> None:
        await self._request(
            "POST", self._p(problem_id, "/settings/enable-groups"), json={"enable": enable, "testset": testset}
        )

    async def enable_points(self, problem_id: int, enable: bool) -> None:
        await self._request("POST", self._p(problem_id, "/settings/enable-points"), json={"enable": enable})

    async def groups(self, problem_id: int, testset: str = TESTSET) -> list[dict]:
        try:
            data = await self._request("GET", self._p(problem_id, f"/groups/{testset}"))
        except PolygonError as e:
            # Polygon answers with an error when groups are disabled
            if e.status in (400, 404, 422):
                return []
            raise
        return list(data or [])

    async def save_group(
        self,
        problem_id: int,
        group: str,
        *,
        points_policy: str,
        feedback_policy: str,
        dependencies: list[str],
        testset: str = TESTSET,
    ) -> None:
        await self._request(
            "PUT",
            self._p(problem_id, f"/groups/{testset}/{quote(group, safe='')}"),
            json={
                "points_policy": points_policy,
                "feedback_policy": feedback_policy,
                "dependencies": dependencies,
            },
        )

    # ------------------------------------------------------------- packages
    async def packages(self, problem_id: int) -> list[dict]:
        return list(await self._request("GET", self._p(problem_id, "/packages")) or [])

    async def build_package(self, problem_id: int, *, full: bool = True, verify: bool = True) -> None:
        await self._request(
            "POST",
            self._p(problem_id, "/packages/build"),
            json={"full": full, "verify": verify, "commit": True},
        )

    async def commit(self, problem_id: int, message: str) -> None:
        await self._request(
            "POST", self._p(problem_id, "/commit"), json={"minor_changes": True, "message": message}
        )

    async def cautions(self, problem_id: int) -> Any:
        try:
            return await self._request("GET", self._p(problem_id, "/cautions"))
        except PolygonError:
            return None
