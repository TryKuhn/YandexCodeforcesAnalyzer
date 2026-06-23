import json
import logging

from aiohttp import ClientSession

logger = logging.getLogger(__name__)


class PolygonAPIError(Exception):
    """Raised when a Polygon API call fails or returns a non-OK status."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        method: str | None = None,
        raw_response: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.raw_response = raw_response

    def __str__(self):
        return self.message


async def get_response(client: ClientSession, url, params):
    """POST to a Polygon endpoint and return the parsed ``result`` payload.

    Decodes the body tolerantly because file contents can carry non-UTF-8 bytes
    (e.g. a solution saved with a broken encoding) and strict decoding would
    raise. Raises ``PolygonAPIError`` on non-OK status or HTTP errors with an
    unparseable body; falls back to ``{"message": ...}`` for OK responses that
    lack a ``result`` field or are not JSON.
    """
    async with client.post(url, data=params) as response:
        raw = await response.read()
        response_text = raw.decode("utf-8", errors="replace")

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            if response.status != 200:
                raise PolygonAPIError(
                    f"HTTP {response.status}: {response_text[:300]}",
                    http_status=response.status,
                    raw_response=response_text,
                )
            else:
                return {"message": response_text}

        if result["status"] == "OK":
            try:
                return result["result"]
            except KeyError:
                return {"message": response_text}

        comment = result.get("comment", "Unknown Polygon error")
        raise PolygonAPIError(
            comment,
            http_status=response.status,
            raw_response=response_text,
        )
