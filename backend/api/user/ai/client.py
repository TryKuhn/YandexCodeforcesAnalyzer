"""Server-side calls into the AI authoring service.

Background jobs (the archive importer) have no user request to forward, so
they mint a short-lived token for the user, exactly like the ones the backend
issues on login.
"""
from datetime import datetime, timezone

import httpx

from api.crypt import create_token
from api.user.polygon.archive.parser import Statement, render_section
from settings import settings

TOKEN_MINUTES = 15
CHECKER_VALIDATOR_TIMEOUT = 600.0

# set by tests
_transport: httpx.AsyncBaseTransport | None = None


class AIServiceError(Exception):
    """The AI service failed or is unreachable."""


def _token(user_id: int) -> str:
    return create_token({"user_id": user_id, "svc": "backend"}, datetime.now(timezone.utc), TOKEN_MINUTES)


def statement_payload(st: Statement) -> dict:
    """A parsed archive statement as the service's ``StatementIn``."""
    return {
        "name": st.title or st.letter,
        "legend": render_section(st.legend),
        "input": render_section(st.input_format),
        "output": render_section(st.output_format),
        "scoring": render_section(st.scoring) or None,
        "notes": render_section(st.notes) or None,
        "time_limit": st.time_limit_ms,
        "memory_limit": st.memory_limit_mb,
        "input_file": st.input_file,
        "output_file": st.output_file,
        "examples": [[str(i), str(o)] for i, o in st.examples[:3]],
    }


async def generate_checker_validator(st: Statement, model: str, *, user_id: int) -> dict:
    """``{"checker": {...}, "validator": {"code": ...}, "comment": str}`` from the service."""
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/ai/assist/checker-validator"
    try:
        async with httpx.AsyncClient(timeout=CHECKER_VALIDATOR_TIMEOUT, transport=_transport) as client:
            response = await client.post(
                url,
                json={"statement": statement_payload(st), "model": model},
                headers={"Authorization": f"Bearer {_token(user_id)}"},
            )
    except httpx.HTTPError as e:
        raise AIServiceError(f"сервис ИИ недоступен: {e!r}") from e
    if response.status_code != 200:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise AIServiceError(f"сервис ИИ: {detail}")
    data = response.json()
    if "checker" not in data or "validator" not in data:
        raise AIServiceError("ответ сервиса ИИ без checker/validator")
    return data
