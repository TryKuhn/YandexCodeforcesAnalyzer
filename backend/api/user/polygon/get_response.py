import json
import logging

from aiohttp import ClientSession

logger = logging.getLogger(__name__)


class PolygonAPIError(Exception):
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
    async with client.post(url, data=params) as response:
        response_text = await response.text()

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
