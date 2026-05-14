import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.http")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/api/health":
            return await call_next(request)

        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        query_params = dict(request.query_params)

        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(
                f"{method} {path} | IP: {client_ip} | Error: {e} | Time: {elapsed:.3f}s"
            )
            raise

        elapsed = time.time() - start_time
        params_str = f" | Params: {query_params}" if query_params else ""
        msg = f"{method} {path} | IP: {client_ip}{params_str} | Status: {response.status_code} | Time: {elapsed:.3f}s"

        if response.status_code >= 500:
            logger.error(msg)
        elif response.status_code >= 400:
            logger.warning(msg)
        else:
            logger.info(msg)

        response.headers["X-Process-Time"] = str(elapsed)
        return response
