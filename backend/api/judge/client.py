"""HTTP client for the judge service; the only place that knows its wire format."""
import base64
from dataclasses import dataclass

import httpx

from settings import settings


class JudgeUnavailable(RuntimeError):
    """The judge service could not be reached or answered with an error."""


@dataclass(frozen=True)
class JudgeTestPayload:
    index: int
    input_data: bytes
    answer_data: bytes
    points: float = 0.0
    group: str | None = None


async def judge_submission(
    *,
    source: bytes,
    language: str,
    checker: bytes,
    tests: list[JudgeTestPayload],
    time_limit_ms: int,
    memory_limit_mb: int,
    timeout_seconds: float = 300.0,
) -> dict:
    """Ask the judge to run one submission and return its raw verdict payload."""
    payload = {
        "source": source.decode(errors="replace"),
        "language": language,
        "checker": checker.decode(errors="replace"),
        "time_limit_ms": time_limit_ms,
        "memory_limit_mb": memory_limit_mb,
        "tests": [
            {
                "index": test.index,
                "input": base64.b64encode(test.input_data).decode(),
                "answer": base64.b64encode(test.answer_data).decode(),
                "points": test.points,
                "group": test.group,
            }
            for test in tests
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{settings.JUDGE_URL}/judge", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        # a judge that is down must not fail the submission, only delay it
        raise JudgeUnavailable(f"judge service unreachable: {exc}") from exc
