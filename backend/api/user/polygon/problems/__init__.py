from fastapi import APIRouter

from api.user.polygon.problems.list import router as list_router
from api.user.polygon.problems.create import router as create_router
from api.user.polygon.problems.detail import router as detail_router
from api.user.polygon.problems.session import router as session_router
from api.user.polygon.problems.statement import router as statement_router
from api.user.polygon.problems.info import router as info_router
from api.user.polygon.problems.files import router as files_router
from api.user.polygon.problems.tests import router as tests_router
from api.user.polygon.problems.packages import router as packages_router
from api.user.polygon.problems.tags import router as tags_router
from api.user.polygon.problems.settings import router as settings_router

problems_router = APIRouter(prefix="/problems")

problems_router.include_router(list_router)
problems_router.include_router(create_router)
problems_router.include_router(detail_router)
problems_router.include_router(session_router)
problems_router.include_router(statement_router)
problems_router.include_router(info_router)
problems_router.include_router(files_router)
problems_router.include_router(tests_router)
problems_router.include_router(packages_router)
problems_router.include_router(tags_router)
problems_router.include_router(settings_router)
