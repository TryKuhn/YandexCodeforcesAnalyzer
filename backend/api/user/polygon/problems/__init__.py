"""``/api/polygon/problems`` — routes over a single Polygon problem."""
from fastapi import APIRouter

from api.user.polygon.problems.create import router as create_router
from api.user.polygon.problems.detail import router as detail_router
from api.user.polygon.problems.files import router as files_router
from api.user.polygon.problems.info import router as info_router
from api.user.polygon.problems.issues import router as issues_router
from api.user.polygon.problems.list import router as list_router
from api.user.polygon.problems.materials import router as materials_router
from api.user.polygon.problems.meta import router as meta_router
from api.user.polygon.problems.packages import router as packages_router
from api.user.polygon.problems.settings import router as settings_router
from api.user.polygon.problems.statement import router as statement_router
from api.user.polygon.problems.tags import router as tags_router
from api.user.polygon.problems.tests import router as tests_router
from api.user.polygon.problems.working_copy import \
    router as working_copy_router

problems_router = APIRouter(prefix="/problems")

for _router in (
    list_router,
    create_router,
    detail_router,
    statement_router,
    info_router,
    meta_router,
    working_copy_router,
    files_router,
    tests_router,
    settings_router,
    packages_router,
    tags_router,
    materials_router,
    issues_router,
):
    problems_router.include_router(_router)
