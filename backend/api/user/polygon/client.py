"""Polygon API core: parameter serialization, signing, response parsing, retries.

Every Polygon call (the wrappers in ``api.user.polygon.methods``, the credential
probe on link, the archive import) goes through :func:`request`, so the rules
are the same everywhere:

* ``None`` means "do not send"; ``bool`` -> ``"true"``/``"false"``;
  list/tuple -> comma-separated string; ``Enum`` -> its ``value``.
* Polygon signs ALL parameters, file contents included. UTF-8 ``bytes`` are
  decoded and sent as text; real binary (not UTF-8, e.g. a statement image) is
  sent as a multipart field -- and is signed byte-for-byte as well.
* ``time`` and the signature are recomputed on every attempt, so a retry after
  a back-off never hits "time is not within 5 minutes".
* Only transient failures are retried: HTTP 5xx, network errors and timeouts,
  a stale timestamp, rate limiting. Logical Polygon errors are raised at once.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Iterable, Mapping
from enum import Enum
from typing import Any, Literal

import aiohttp
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.create_signature import create_signature
from models import User
from settings import settings

logger = logging.getLogger(__name__)

ResponseKind = Literal["json", "text", "bytes"]

MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 1.5
RETRY_HTTP_STATUSES = frozenset({500, 502, 503, 504})
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=300)
_TRANSIENT_COMMENT_MARKERS = (
    "not within 5 minutes",
    "too many",
    "try again later",
    "limit exceeded",
)

# Methods with side effects that must not run twice: after a 5xx / timeout we do
# not know whether Polygon executed them, so only "rejected before execution"
# errors (stale time, rate limit) are retried for these.
NOT_REPEATABLE_METHODS = frozenset({
    "problem.create",
    "problem.buildPackage",
    "problem.addIssue",
    "problem.updateIssue",
})

# Module-level so tests can skip the back-off.
_sleep = asyncio.sleep


class PolygonAPIError(Exception):
    """A Polygon API failure (status=FAILED, HTTP or network error) or a bad parameter.

    ``result`` is the payload of a FAILED response when Polygon sends one
    (e.g. ``DeleteTestsResult`` for ``problem.deleteTest``).
    """

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        method: str | None = None,
        raw_response: str | None = None,
        result: Any = None,
        retryable: bool | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.method = method
        self.raw_response = raw_response
        self.result = result
        # None: decide from the status / message (see _is_transient).
        self.retryable = retryable

    def __str__(self) -> str:
        return self.message


class PolygonParamError(PolygonAPIError):
    """A parameter rejected locally, before any request is sent (HTTP 422)."""

    def __init__(self, message: str, *, method: str | None = None):
        super().__init__(message, http_status=422, method=method, retryable=False)


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
def decode_text(data: bytes) -> str:
    """Decode bytes as text: UTF-8, then cp1251, latin-1 as the last resort."""
    for encoding in ("utf-8", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def encode_param(value: Any) -> str | bytes | None:
    """Encode a parameter value the way Polygon expects (see the module docstring)."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return encode_param(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        parts = [encode_param(v) for v in value]
        return ",".join(p.decode() if isinstance(p, bytes) else p for p in parts if p is not None)
    return str(value)


def split_params(params: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, bytes]]:
    """Split parameters into text fields and binary (multipart) fields."""
    text: dict[str, str] = {}
    binary: dict[str, bytes] = {}
    for key, raw in params.items():
        value = encode_param(raw)
        if value is None:
            continue
        if isinstance(value, bytes):
            try:
                text[key] = value.decode("utf-8")
            except UnicodeDecodeError:
                binary[key] = value
        else:
            text[key] = value
    return text, binary


def signed_form(
    method: str,
    text_params: Mapping[str, str],
    api_key: str,
    api_secret: str,
    binary_params: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Add ``apiKey``/``time`` and sign the request (``apiSig``).

    Binary params take part in the signature and are returned in the form too.
    """
    form: dict[str, Any] = {
        "apiKey": api_key, "time": str(int(time.time())), **text_params, **(binary_params or {})
    }
    form["apiSig"] = create_signature(method, form, api_secret)
    return form


def choice(
    value: Any, allowed: Iterable[str], name: str, *, method: str | None = None
) -> str | None:
    """Normalize an enum-like value (case, ``-`` -> ``_``) and validate it.

    ``None`` passes through. The canonical case comes from ``allowed`` (Polygon
    has both ``COMPLETE_GROUP`` and ``resource``).
    """
    if value is None:
        return None
    raw = value.value if isinstance(value, Enum) else value
    normalized = str(raw).strip().replace("-", "_")
    for candidate in allowed:
        if candidate.lower() == normalized.lower():
            return candidate
    raise PolygonParamError(
        f"{name}: недопустимое значение {raw!r}; допустимо: {', '.join(allowed)}",
        method=method,
    )


def one_of(method: str, **params: Any) -> None:
    """Check that exactly one of mutually exclusive parameters is given."""
    given = [k for k, v in params.items() if v is not None]
    if len(given) != 1:
        raise PolygonParamError(
            f"{method}: нужно указать ровно один из параметров {', '.join(params)}",
            method=method,
        )


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
def _envelope(text: str) -> dict | None:
    """Return the ``{status, result|comment}`` envelope if the body is one."""
    if not text.lstrip().startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, dict) and data.get("status") in ("OK", "FAILED"):
        return data
    return None


def parse_response(method: str, http_status: int, body: bytes, kind: ResponseKind) -> Any:
    """Parse a Polygon response.

    ``json``: return the envelope's ``result`` (``None`` when absent).
    ``text``/``bytes``: raw methods (viewFile, testInput, package, ...); on
    HTTP 200 the body is returned as is unless it is a FAILED envelope.
    """
    text = body.decode("utf-8", errors="replace")
    envelope = _envelope(text)

    if envelope is not None and envelope["status"] == "FAILED":
        raise PolygonAPIError(
            envelope.get("comment") or "Unknown Polygon error",
            http_status=http_status,
            method=method,
            raw_response=text,
            result=envelope.get("result"),
        )

    if http_status != 200:
        if "<html" in text[:500].lower():
            message = f"HTTP {http_status}: сервер Polygon временно недоступен (ошибка шлюза)"
        else:
            message = f"HTTP {http_status}: {text[:300]}"
        raise PolygonAPIError(message, http_status=http_status, method=method, raw_response=text)

    if kind == "bytes":
        return body
    if kind == "text":
        return decode_text(body)
    if envelope is None:
        raise PolygonAPIError(
            f"{method}: неожиданный ответ Polygon: {text[:300]}",
            http_status=502,
            method=method,
            raw_response=text,
            retryable=False,
        )
    return envelope.get("result")


def _rejected_before_execution(error: PolygonAPIError) -> bool:
    """Stale timestamp / rate limit: Polygon refused the call without running it."""
    message = error.message.lower()
    return any(marker in message for marker in _TRANSIENT_COMMENT_MARKERS)


def _is_transient(error: PolygonAPIError, method: str) -> bool:
    if method in NOT_REPEATABLE_METHODS:
        return _rejected_before_execution(error)
    if error.retryable is not None:
        return error.retryable
    return error.http_status in RETRY_HTTP_STATUSES or _rejected_before_execution(error)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def method_url(method: str) -> str:
    """Method URL: ``POLYGON_HOST/<method>``."""
    return f"{settings.POLYGON_HOST.rstrip('/')}/{method}"


async def _post(
    session: aiohttp.ClientSession | None, url: str, form: dict
) -> tuple[int, bytes]:
    if session is None:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as own:
            return await _post(own, url, form)
    async with session.post(url, data=form) as response:
        return response.status, await response.read()


async def request(
    method: str,
    params: Mapping[str, Any],
    *,
    api_key: str,
    api_secret: str,
    kind: ResponseKind = "json",
    session: aiohttp.ClientSession | None = None,
) -> Any:
    """Sign and perform a ``method`` call, retrying transient failures."""
    text_params, binary_params = split_params(params)
    url = method_url(method)
    last_error = PolygonAPIError(f"{method}: неизвестная ошибка", method=method)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        form = signed_form(method, text_params, api_key, api_secret, binary_params)
        try:
            http_status, body = await _post(session, url, form)
            return parse_response(method, http_status, body, kind)
        except PolygonAPIError as e:
            if not _is_transient(e, method):
                raise
            last_error = e
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = PolygonAPIError(
                f"{method}: Polygon недоступен ({e!r})",
                http_status=502,
                method=method,
                retryable=True,
            )
            if method in NOT_REPEATABLE_METHODS:
                raise last_error from e
        if attempt < MAX_ATTEMPTS:
            logger.warning(
                f"Polygon {method}: {last_error}; повтор {attempt}/{MAX_ATTEMPTS - 1}"
            )
            await _sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise last_error


# ---------------------------------------------------------------------------
# Calls on behalf of a user
# ---------------------------------------------------------------------------
async def get_user(user_id: int, db: AsyncSession) -> User:
    """The user with Polygon credentials configured, otherwise HTTP 401."""
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user or not user.polygon_api_key or not user.polygon_api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )
    return user


async def call(
    method: str,
    user_id: int,
    db: AsyncSession,
    *,
    kind: ResponseKind = "json",
    **params: Any,
) -> Any:
    """Call a Polygon method with the credentials of ``user_id``."""
    user = await get_user(user_id, db)
    return await request(
        method,
        params,
        api_key=user.polygon_api_key or "",
        api_secret=user.polygon_api_secret or "",
        kind=kind,
    )
