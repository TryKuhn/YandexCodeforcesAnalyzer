"""``/api/ai/*`` -> the AI authoring service.

The frontend keeps a single API origin; the backend checks the token (the
service checks it again) and forwards the request with its body, query and
``Authorization`` header. Long synchronous calls (a solution draft) are
covered by ``AI_PROXY_TIMEOUT_SECONDS``.
"""
import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from settings import settings

logger = logging.getLogger(__name__)

ai_proxy_router = APIRouter()

_FORWARD_REQUEST_HEADERS = ("authorization", "content-type", "accept", "accept-language")
_FORWARD_RESPONSE_HEADERS = ("content-type", "content-disposition", "cache-control")

# set by tests; production uses a real network transport
_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_client_transport: httpx.AsyncBaseTransport | None = None


def _get_client() -> httpx.AsyncClient:
    """One pooled client per process (recreated when tests swap the transport)."""
    global _client, _client_transport
    if _client is None or _client.is_closed or _client_transport is not _transport:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.AI_PROXY_TIMEOUT_SECONDS, connect=5.0),
            transport=_transport,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        _client_transport = _transport
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


@ai_proxy_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def route_ai_proxy(path: str, request: Request) -> Response:
    """Forward the request to the AI service and relay its answer."""
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/ai/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_REQUEST_HEADERS}
    try:
        upstream = await _get_client().request(
            request.method,
            url,
            params=list(request.query_params.multi_items()),
            content=await request.body(),
            headers=headers,
        )
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"detail": "Сервис ИИ не ответил вовремя"})
    except httpx.HTTPError as e:
        logger.warning(f"AI service unreachable: {e!r}")
        return JSONResponse(status_code=503, content={"detail": "Сервис ИИ недоступен"})

    response_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() in _FORWARD_RESPONSE_HEADERS
    }
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)
