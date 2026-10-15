"""Every wrapper in ``api.user.polygon.methods`` → exact Polygon call.

One row per Polygon method: how we call the wrapper, which API method it must
hit, with which serialized parameters and response kind. ``problemId`` is
always 555 and ``None`` options are never sent.
"""
import pytest

from api.user.polygon import methods as m

P = {"problemId": "555"}

CASES = [
    # name, call(u, db), method, params, kind
    ("list_problems", lambda u, d: m.list_problems(u, d),
     "problems.list", {}, "json"),
    ("list_problems_filters",
     lambda u, d: m.list_problems(u, d, show_deleted=True, problem_id=7, name="a", owner="o"),
     "problems.list", {"showDeleted": "true", "id": "7", "name": "a", "owner": "o"}, "json"),
    ("create_problem", lambda u, d: m.create_problem("a-plus-b", u, d),
     "problem.create", {"name": "a-plus-b"}, "json"),
    ("get_contest_problems", lambda u, d: m.get_contest_problems(9, u, d),
     "contest.problems", {"contestId": "9"}, "json"),
    # info / meta
    ("get_info", lambda u, d: m.get_info(555, u, d), "problem.info", P, "json"),
    ("update_info", lambda u, d: m.update_info(
        555, u, d, input_file="in.txt", output_file="out.txt", interactive=False,
        well_formed=True, skip_duplicated_tests_validation=True, time_limit=1000,
        memory_limit=256),
     "problem.updateInfo",
     {**P, "inputFile": "in.txt", "outputFile": "out.txt", "interactive": "false",
      "wellFormed": "true", "skipDuplicatedTestsValidation": "true",
      "timeLimit": "1000", "memoryLimit": "256"}, "json"),
    ("update_info_partial", lambda u, d: m.update_info(555, u, d, interactive=True),
     "problem.updateInfo", {**P, "interactive": "true"}, "json"),
    ("get_note", lambda u, d: m.get_note(555, u, d), "problem.note", P, "json"),
    ("save_note", lambda u, d: m.save_note(555, "wip", u, d),
     "problem.saveNote", {**P, "note": "wip"}, "json"),
    ("view_tags", lambda u, d: m.view_tags(555, u, d), "problem.viewTags", P, "json"),
    ("save_tags", lambda u, d: m.save_tags(555, ["dp", "math"], u, d),
     "problem.saveTags", {**P, "tags": "dp,math"}, "json"),
    ("view_general_description", lambda u, d: m.view_general_description(555, u, d),
     "problem.viewGeneralDescription", P, "json"),
    ("save_general_description", lambda u, d: m.save_general_description(555, "D", u, d),
     "problem.saveGeneralDescription", {**P, "description": "D"}, "json"),
    ("view_general_tutorial", lambda u, d: m.view_general_tutorial(555, u, d),
     "problem.viewGeneralTutorial", P, "json"),
    ("save_general_tutorial", lambda u, d: m.save_general_tutorial(555, "T", u, d),
     "problem.saveGeneralTutorial", {**P, "tutorial": "T"}, "json"),
    ("get_accesses", lambda u, d: m.get_accesses(555, u, d), "problem.accesses", P, "json"),
    ("set_access", lambda u, d: m.set_access(555, "bob", "write", u, d),
     "problem.setAccess", {**P, "login": "bob", "accessType": "WRITE"}, "json"),
    # working copy
    ("update_working_copy", lambda u, d: m.update_working_copy(555, u, d),
     "problem.updateWorkingCopy", P, "json"),
    ("discard_working_copy", lambda u, d: m.discard_working_copy(555, u, d),
     "problem.discardWorkingCopy", P, "json"),
    ("commit_changes", lambda u, d: m.commit_changes(555, u, d, minor_changes=True, message="m"),
     "problem.commitChanges", {**P, "minorChanges": "true", "message": "m"}, "json"),
    # statements
    ("get_statements", lambda u, d: m.get_statements(555, u, d),
     "problem.statements", P, "json"),
    ("render_statements", lambda u, d: m.render_statements(555, u, d, include_content=True),
     "problem.renderStatements", {**P, "includeContent": "true"}, "json"),
    ("save_statement", lambda u, d: m.save_statement(
        555, "russian", u, d, encoding="utf-8", name="N", legend="L", input="I",
        output="O", notes="", show_in_review=False),
     "problem.saveStatement",
     {**P, "lang": "russian", "encoding": "utf-8", "name": "N", "legend": "L",
      "input": "I", "output": "O", "notes": "", "showInReview": "false"}, "json"),
    ("get_statement_resources", lambda u, d: m.get_statement_resources(555, u, d),
     "problem.statementResources", P, "json"),
    ("view_statement_resource", lambda u, d: m.view_statement_resource(555, "a.png", u, d),
     "problem.viewStatementResource", {**P, "name": "a.png"}, "bytes"),
    ("save_statement_resource", lambda u, d: m.save_statement_resource(
        555, "a.png", b"\x89PNG\xff", u, d, check_existing=False),
     "problem.saveStatementResource",
     {**P, "name": "a.png", "file": b"\x89PNG\xff", "checkExisting": "false"}, "json"),
    # files
    ("get_files", lambda u, d: m.get_files(555, u, d), "problem.files", P, "json"),
    ("view_file", lambda u, d: m.view_file(555, "SOURCE", "g.cpp", u, d),
     "problem.viewFile", {**P, "type": "source", "name": "g.cpp"}, "text"),
    ("view_file_bytes", lambda u, d: m.view_file_bytes(555, "resource", "i.png", u, d),
     "problem.viewFile", {**P, "type": "resource", "name": "i.png"}, "bytes"),
    ("save_file", lambda u, d: m.save_file(
        555, "source", "g.cpp", "code", u, d, source_type="cpp.g++17", check_existing=True),
     "problem.saveFile",
     {**P, "type": "source", "name": "g.cpp", "file": "code", "sourceType": "cpp.g++17",
      "checkExisting": "true"}, "json"),
    ("save_file_resource_advanced", lambda u, d: m.save_file(
        555, "resource", "grader.cpp", "x", u, d,
        for_types="cpp.*", stages="COMPILE", assets="SOLUTION"),
     "problem.saveFile",
     {**P, "type": "resource", "name": "grader.cpp", "file": "x", "forTypes": "cpp.*",
      "stages": "COMPILE", "assets": "SOLUTION"}, "json"),
    # checker / validator / interactor
    ("get_checker", lambda u, d: m.get_checker(555, u, d), "problem.checker", P, "json"),
    ("set_checker", lambda u, d: m.set_checker(555, "std::wcmp.cpp", u, d),
     "problem.setChecker", {**P, "checker": "std::wcmp.cpp"}, "json"),
    ("get_validator", lambda u, d: m.get_validator(555, u, d), "problem.validator", P, "json"),
    ("set_validator", lambda u, d: m.set_validator(555, "v.cpp", u, d),
     "problem.setValidator", {**P, "validator": "v.cpp"}, "json"),
    ("get_extra_validators", lambda u, d: m.get_extra_validators(555, u, d),
     "problem.extraValidators", P, "json"),
    ("get_interactor", lambda u, d: m.get_interactor(555, u, d),
     "problem.interactor", P, "json"),
    ("set_interactor", lambda u, d: m.set_interactor(555, "i.cpp", u, d),
     "problem.setInteractor", {**P, "interactor": "i.cpp"}, "json"),
    ("get_validator_tests", lambda u, d: m.get_validator_tests(555, u, d),
     "problem.validatorTests", P, "json"),
    ("save_validator_test", lambda u, d: m.save_validator_test(
        555, 3, u, d, test_input="1 2", test_verdict="invalid", testset="tests"),
     "problem.saveValidatorTest",
     {**P, "testIndex": "3", "testInput": "1 2", "testVerdict": "INVALID",
      "testset": "tests"}, "json"),
    ("get_checker_tests", lambda u, d: m.get_checker_tests(555, u, d),
     "problem.checkerTests", P, "json"),
    ("save_checker_test", lambda u, d: m.save_checker_test(
        555, 1, u, d, test_input="1", test_output="2", test_answer="2",
        test_verdict="wrong-answer"),
     "problem.saveCheckerTest",
     {**P, "testIndex": "1", "testInput": "1", "testOutput": "2", "testAnswer": "2",
      "testVerdict": "WRONG_ANSWER"}, "json"),
    # solutions
    ("get_solutions", lambda u, d: m.get_solutions(555, u, d), "problem.solutions", P, "json"),
    ("view_solution", lambda u, d: m.view_solution(555, "main.cpp", u, d),
     "problem.viewSolution", {**P, "name": "main.cpp"}, "text"),
    ("save_solution", lambda u, d: m.save_solution(
        555, "wa.py", "print(1)", u, d, tag="wa", source_type="python.3"),
     "problem.saveSolution",
     {**P, "name": "wa.py", "file": "print(1)", "tag": "WA", "sourceType": "python.3"},
     "json"),
    ("edit_solution_extra_tags_add", lambda u, d: m.edit_solution_extra_tags(
        555, "tl.cpp", False, u, d, test_group="2", tag="TL"),
     "problem.editSolutionExtraTags",
     {**P, "name": "tl.cpp", "remove": "false", "testGroup": "2", "tag": "TL"}, "json"),
    ("edit_solution_extra_tags_remove", lambda u, d: m.edit_solution_extra_tags(
        555, "tl.cpp", True, u, d, testset="tests", tag="TL"),
     "problem.editSolutionExtraTags",
     {**P, "name": "tl.cpp", "remove": "true", "testset": "tests"}, "json"),
    # scripts / tests
    ("get_script", lambda u, d: m.get_script(555, "tests", u, d),
     "problem.script", {**P, "testset": "tests"}, "text"),
    ("save_script", lambda u, d: m.save_script(555, "tests", "gen > $", u, d),
     "problem.saveScript", {**P, "testset": "tests", "source": "gen > $"}, "json"),
    ("clear_script", lambda u, d: m.clear_script(555, "tests", u, d),
     "problem.clearScript", {**P, "testset": "tests"}, "json"),
    ("get_tests", lambda u, d: m.get_tests(555, "tests", u, d, no_inputs=True),
     "problem.tests", {**P, "testset": "tests", "noInputs": "true"}, "json"),
    ("preview_tests", lambda u, d: m.preview_tests(555, "tests", u, d),
     "problem.previewTests", {**P, "testset": "tests"}, "json"),
    ("get_test_input", lambda u, d: m.get_test_input(555, "tests", 4, u, d),
     "problem.testInput", {**P, "testset": "tests", "testIndex": "4"}, "text"),
    ("get_test_answer", lambda u, d: m.get_test_answer(555, "tests", 4, u, d),
     "problem.testAnswer", {**P, "testset": "tests", "testIndex": "4"}, "text"),
    ("save_test", lambda u, d: m.save_test(
        555, "tests", 2, b"5 6\n", u, d, check_existing=False, test_group="1",
        test_points=12.5, test_description="d", test_use_in_statements=True,
        test_input_for_statements="i", test_output_for_statements="o",
        verify_input_output_for_statements=False),
     "problem.saveTest",
     {**P, "testset": "tests", "testIndex": "2", "testInput": "5 6\n",
      "checkExisting": "false", "testGroup": "1", "testPoints": "12.5",
      "testDescription": "d", "testUseInStatements": "true",
      "testInputForStatements": "i", "testOutputForStatements": "o",
      "verifyInputOutputForStatements": "false"}, "json"),
    ("save_test_metadata_only", lambda u, d: m.save_test(
        555, "tests", 7, None, u, d, test_points=40),
     "problem.saveTest",
     {**P, "testset": "tests", "testIndex": "7", "testPoints": "40.0"}, "json"),
    ("delete_tests", lambda u, d: m.delete_tests(555, "tests", [3, 4, 5], u, d),
     "problem.deleteTest", {**P, "testset": "tests", "testIndices": "3,4,5"}, "json"),
    ("set_test_group", lambda u, d: m.set_test_group(555, "tests", "2", (6, 7), u, d),
     "problem.setTestGroup",
     {**P, "testset": "tests", "testGroup": "2", "testIndices": "6,7"}, "json"),
    # groups / points
    ("enable_groups", lambda u, d: m.enable_groups(555, "tests", True, u, d),
     "problem.enableGroups", {**P, "testset": "tests", "enable": "true"}, "json"),
    ("enable_points", lambda u, d: m.enable_points(555, False, u, d),
     "problem.enablePoints", {**P, "enable": "false"}, "json"),
    ("enable_treat_points_from_checker_as_percent", lambda u, d: m.enable_treat_points_from_checker_as_percent(
        555, True, u, d),
     "problem.enableTreatPointsFromCheckerAsPercent", {**P, "enable": "true"}, "json"),
    ("view_test_group", lambda u, d: m.view_test_group(555, "tests", u, d, group="1"),
     "problem.viewTestGroup", {**P, "testset": "tests", "group": "1"}, "json"),
    ("save_test_group", lambda u, d: m.save_test_group(
        555, "tests", "2", u, d, points_policy="complete-group",
        feedback_policy="icpc", dependencies=["0", "1"]),
     "problem.saveTestGroup",
     {**P, "testset": "tests", "group": "2", "pointsPolicy": "COMPLETE_GROUP",
      "feedbackPolicy": "ICPC", "dependencies": "0,1"}, "json"),
    # packages
    ("get_packages", lambda u, d: m.get_packages(555, u, d), "problem.packages", P, "json"),
    ("download_package", lambda u, d: m.download_package(555, 42, u, d, package_type="linux"),
     "problem.package", {**P, "packageId": "42", "type": "linux"}, "bytes"),
    ("build_package", lambda u, d: m.build_package(555, u, d, full=True, verify=False),
     "problem.buildPackage", {**P, "full": "true", "verify": "false"}, "json"),
    # materials
    ("get_materials", lambda u, d: m.get_materials(555, u, d), "problem.materials", P, "json"),
    ("save_material", lambda u, d: m.save_material(
        555, "pack", "with_tutorial", [{"type": "SOLUTIONS", "names": ["main.cpp"]}], u, d,
        original_name="old"),
     "problem.setMaterial",
     {**P, "name": "pack", "originalName": "old", "publishStrategy": "WITH_TUTORIAL",
      "items": '[{"type":"SOLUTIONS","names":["main.cpp"]}]'}, "json"),
    ("remove_material", lambda u, d: m.remove_material(555, "pack", u, d),
     "problem.setMaterial", {**P, "name": "pack", "remove": "true"}, "json"),
    # cautions / issues
    ("get_cautions", lambda u, d: m.get_cautions(555, u, d), "problem.cautions", P, "json"),
    ("get_issues", lambda u, d: m.get_issues(555, u, d), "problem.issues", P, "json"),
    ("add_issue", lambda u, d: m.add_issue(555, "bug", "**broken**", u, d, assignee="bob"),
     "problem.addIssue", {**P, "type": "BUG", "content": "**broken**", "assignee": "bob"},
     "json"),
    ("update_issue", lambda u, d: m.update_issue(
        555, 17, u, d, comment="done", status="closed", assignee=""),
     "problem.updateIssue",
     {**P, "issueId": "17", "comment": "done", "status": "CLOSED", "assignee": ""}, "json"),
]


@pytest.mark.parametrize(
    "call,method,params,kind", [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
async def test_wrapper_sends_exact_request(polygon_api, db, user, call, method, params, kind):
    polygon_api.respond("problem.create", {"id": 1})
    await call(user.id, db)
    sent = polygon_api.last()
    assert (sent.method, sent.params, sent.kind) == (method, params, kind)
    assert (sent.api_key, sent.api_secret) == ("key", "secret")


def test_every_public_wrapper_is_covered():
    """A new wrapper must get a row above."""
    covered = {c[0] for c in CASES}
    names = {n for n in m.__all__ if not n.startswith("upload_")}
    missing = {n for n in names if not any(c.startswith(n) for c in covered)}
    assert missing == set()
