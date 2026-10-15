"""Polygon integration: the ``/api/polygon`` routes and the Polygon API client.

* ``client`` -- the core (signing, serialization, response parsing, retries);
* ``methods`` -- wrappers of every API method, one function per method;
* ``cache`` -- refresh of the local problem/statement/solution cache;
* ``problems``/``contests``/``archive``/``auth`` -- routers.
"""
from api.user.polygon.archive import archive_router
from api.user.polygon.auth.login import link_polygon
from api.user.polygon.auth.logout import unlink_polygon
from api.user.polygon.base_polygon import polygon_router
from api.user.polygon.client import (PolygonAPIError, PolygonParamError, call,
                                     get_user, request)
from api.user.polygon.contests import contests_router
from api.user.polygon.problems import problems_router

polygon_router.include_router(problems_router)
polygon_router.include_router(contests_router)
polygon_router.include_router(archive_router)

__all__ = [
    "polygon_router",
    "problems_router",
    "contests_router",
    "archive_router",
    "link_polygon",
    "unlink_polygon",
    "PolygonAPIError",
    "PolygonParamError",
    "call",
    "get_user",
    "request",
]
