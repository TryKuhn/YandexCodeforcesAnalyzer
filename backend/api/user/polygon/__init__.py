from api.user.polygon.auth.login import link_polygon
from api.user.polygon.auth.logout import unlink_polygon
from api.user.polygon.base_polygon import polygon_router
from api.user.polygon.problems import problems_router
from api.user.polygon.archive import archive_router
from api.user.polygon.client import get_user, polygon_call, polygon_call_binary
from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import PolygonAPIError, get_response

# Problem
from api.user.polygon.problem.get.info import get_problem_info
from api.user.polygon.problem.get.list import list_problems
from api.user.polygon.problem.get.packages import get_packages
from api.user.polygon.problem.get.tags import view_tags
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.post.create import create_problem
from api.user.polygon.problem.post.package import build_package

# Problem settings
from api.user.polygon.problem.settings.enable_groups import enable_groups
from api.user.polygon.problem.settings.enable_points import enable_points
from api.user.polygon.problem.settings.save_test_group import save_test_group
from api.user.polygon.problem.settings.set_tags import set_tags
from api.user.polygon.problem.settings.set_test_group import set_test_group
from api.user.polygon.problem.settings.update_info import update_info

# Statement
from api.user.polygon.statement.get.setatement import get_statements
from api.user.polygon.statement.post.statement import save_statement

# Files
from api.user.polygon.files.checker.post.set_checker import set_checker
from api.user.polygon.files.generator.post.save_file import set_generator
from api.user.polygon.files.interactor.post.set_interactor import set_interactor
from api.user.polygon.files.script.post.save_script import save_script
from api.user.polygon.files.solution.post.save_solution import save_solution
from api.user.polygon.files.test.post.save_test import save_test
from api.user.polygon.files.validator.post.set_validator import set_validator
from api.user.polygon.files.get.files import get_files
from api.user.polygon.files.get.view_file import view_file
from api.user.polygon.files.solution.get.view_solution import view_solution
from api.user.polygon.files.test.get.tests import get_tests

polygon_router.include_router(problems_router)
polygon_router.include_router(archive_router)

__all__ = [
    # Auth & router
    "link_polygon",
    "problems_router",
    "unlink_polygon",
    "polygon_router",
    # Client utilities
    "get_user",
    "polygon_call",
    "polygon_call_binary",
    "create_signature",
    "get_response",
    "PolygonAPIError",
    # Problem
    "create_problem",
    "get_problem_info",
    "list_problems",
    "get_packages",
    "view_tags",
    "commit_changes",
    "build_package",
    # Problem settings
    "enable_groups",
    "enable_points",
    "save_test_group",
    "set_tags",
    "set_test_group",
    "update_info",
    # Statement
    "get_statements",
    "save_statement",
    # Files
    "set_checker",
    "set_generator",
    "set_interactor",
    "save_script",
    "save_solution",
    "save_test",
    "set_validator",
    "get_files",
    "view_file",
    "view_solution",
    "get_tests",
]
