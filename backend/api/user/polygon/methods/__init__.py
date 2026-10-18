"""Wrappers of every Polygon API method (https://codeforces.github.io/polygon-misc/API).

One function per Polygon method (plus the ``upload_*`` composites), one shape:

    async def <method>(problem_id, <required params>, user_id, db, *, <optional params>)

* names are the snake_cased method; "noun" methods get a ``get_`` prefix
  (``problem.tests`` -> ``get_tests``), ``problem.package`` -> ``download_package``;
* an optional parameter set to ``None`` is not sent; an empty string IS sent
  (that is how fields are cleared);
* enum-like values are validated against ``constants`` before the request
  (``PolygonParamError``, HTTP 422); Polygon errors raise ``PolygonAPIError``;
* JSON methods return ``result``; raw ones return ``str`` (viewFile,
  viewSolution, script, testInput, testAnswer) or ``bytes`` (package,
  viewStatementResource); methods without a useful result return ``None``.

DB caching (problem list, info, statements, solutions) lives in
``api.user.polygon.cache``.
"""
from api.user.polygon.methods.checking import (get_checker, get_checker_tests,
                                               get_extra_validators,
                                               get_interactor, get_validator,
                                               get_validator_tests,
                                               save_checker_test,
                                               save_validator_test,
                                               set_checker, set_interactor,
                                               set_validator, upload_checker,
                                               upload_interactor,
                                               upload_validator)
from api.user.polygon.methods.files import (get_files, save_file, view_file,
                                            view_file_bytes)
from api.user.polygon.methods.groups import (
    enable_groups, enable_points, enable_treat_points_from_checker_as_percent,
    save_test_group, view_test_group)
from api.user.polygon.methods.info import (get_accesses, get_info, get_note,
                                           save_general_description,
                                           save_general_tutorial, save_note,
                                           save_tags, set_access, update_info,
                                           view_general_description,
                                           view_general_tutorial, view_tags)
from api.user.polygon.methods.issues import (add_issue, get_cautions,
                                             get_issues, update_issue)
from api.user.polygon.methods.materials import (get_materials, remove_material,
                                                save_material)
from api.user.polygon.methods.packages import (build_package, download_package,
                                               get_packages)
from api.user.polygon.methods.problems import (create_problem,
                                               get_contest_problems,
                                               list_problems)
from api.user.polygon.methods.solutions import (edit_solution_extra_tags,
                                                get_solutions, save_solution,
                                                view_solution)
from api.user.polygon.methods.statements import (get_statement_resources,
                                                 get_statements,
                                                 render_statements,
                                                 save_statement,
                                                 save_statement_resource,
                                                 view_statement_resource)
from api.user.polygon.methods.testsets import (clear_script, delete_tests,
                                               get_script, get_test_answer,
                                               get_test_input, get_tests,
                                               preview_tests, save_script,
                                               save_test, set_test_group)
from api.user.polygon.methods.working_copy import (commit_changes,
                                                   discard_working_copy,
                                                   update_working_copy)

__all__ = [
    # problems.list / problem.create / contest.problems
    "list_problems", "create_problem", "get_contest_problems",
    # info, note, tags, general description/tutorial, accesses
    "get_info", "update_info", "get_note", "save_note", "view_tags", "save_tags",
    "view_general_description", "save_general_description",
    "view_general_tutorial", "save_general_tutorial", "get_accesses", "set_access",
    # working copy
    "update_working_copy", "discard_working_copy", "commit_changes",
    # statements
    "get_statements", "render_statements", "save_statement",
    "get_statement_resources", "view_statement_resource", "save_statement_resource",
    # files
    "get_files", "view_file", "view_file_bytes", "save_file",
    # checker / validator / interactor
    "get_checker", "set_checker", "get_validator", "set_validator",
    "get_extra_validators", "get_interactor", "set_interactor",
    "upload_checker", "upload_validator", "upload_interactor",
    "get_validator_tests", "save_validator_test", "get_checker_tests", "save_checker_test",
    # solutions
    "get_solutions", "view_solution", "save_solution", "edit_solution_extra_tags",
    # scripts and tests
    "get_script", "save_script", "clear_script", "get_tests", "preview_tests",
    "get_test_input", "get_test_answer", "save_test", "delete_tests", "set_test_group",
    # groups and points
    "enable_groups", "enable_points", "enable_treat_points_from_checker_as_percent",
    "view_test_group", "save_test_group",
    # packages
    "get_packages", "download_package", "build_package",
    # materials
    "get_materials", "save_material", "remove_material",
    # cautions and issues
    "get_cautions", "get_issues", "add_issue", "update_issue",
]
