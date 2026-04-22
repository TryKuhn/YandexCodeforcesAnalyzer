import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger('fastapi')


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        client_ip = request.client.host if request.client else 'unknown'

        logger.debug(f'{method} {path} | IP: {client_ip} | Params: '
                     f'{query_params if query_params else "none"}')

        try:
            response = await call_next(request)

            process_time = time.time() - start_time

            log_msg = f'{method} {path} | Status: {response.status_code} | Time: {process_time:.3f}s'

            if response.status_code >= 500:
                logger.error(log_msg)
            elif response.status_code >= 400:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

            response.headers['X-Process-Time'] = str(process_time)

            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(f'{method} {path} | Error: {str(e)} | Time: {process_time:.3f}s')

            raise
