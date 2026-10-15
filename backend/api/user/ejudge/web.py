"""ejudge web interface: reload the contest configuration after serve.cfg changed.

The same calls algolymp (github.com/Gornak40/algolymp) makes:

* ``serve-control`` login -> the session id is in the redirect URL (``SID``);
* ``new-master`` ``action=3`` with ``contest_id`` -> a master session (``SID``);
* ``new-master`` ``action=62`` -> "reload config files".
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from api.user.ejudge.common import EjudgeError

ACTION_MASTER_LOGIN = "3"
ACTION_RELOAD_CONFIG = "62"

# set by tests
_transport: httpx.AsyncBaseTransport | None = None


def _sid(response: httpx.Response) -> str | None:
    query = parse_qs(urlparse(str(response.url)).query)
    values = query.get("SID") or []
    sid = values[0] if values else ""
    return sid if sid.strip("0") else None


class EjudgeWeb:
    def __init__(self, url: str, login: str, password: str) -> None:
        self.base = url.rstrip("/")
        self.login_name = login
        self.password = password

    async def _post(self, client: httpx.AsyncClient, script: str, data: dict) -> httpx.Response:
        try:
            response = await client.post(f"{self.base}/{script}", data=data)
        except httpx.HTTPError as e:
            raise EjudgeError(f"ejudge web недоступен: {e!r}") from e
        if response.status_code != 200:
            raise EjudgeError(f"ejudge web: HTTP {response.status_code} на {script}")
        return response

    async def reload_config(self, contest_id: int) -> None:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60, transport=_transport) as client:
            login = await self._post(
                client, "serve-control", {"login": self.login_name, "password": self.password}
            )
            sid = _sid(login)
            if not sid:
                raise EjudgeError("ejudge: не удалось войти в serve-control (проверьте логин и пароль)")
            master = await self._post(
                client, "new-master",
                {"contest_id": str(contest_id), "SID": sid, "action": ACTION_MASTER_LOGIN},
            )
            csid = _sid(master)
            if not csid:
                raise EjudgeError(f"ejudge: нет прав администратора контеста {contest_id}")
            await self._post(client, "new-master", {"SID": csid, "action": ACTION_RELOAD_CONFIG})
