"""Unit tests for api/user/polygon/problems/files.py route handlers."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.polygon_task import (
    EditSolutionExtraTagsRequest, SaveCheckerTestRequest, SaveFileRequest,
    SaveScriptRequest, SaveSolutionRequest, SaveValidatorTestRequest,
    SetCheckerRequest, SetInteractorRequest, SetValidatorRequest)
from api.user.polygon.client import PolygonAPIError, PolygonParamError
from api.user.polygon.problems import files as r

P = {"problemId": "555"}


async def test_route_get_files_merges_solutions(polygon_api, db, user):
    polygon_api.respond("problem.files", {"resourceFiles": [{"name": "a"}], "sourceFiles": []})
    polygon_api.respond("problem.solutions", [{"name": "sol.cpp", "tag": "MA"}])

    result = await r.route_get_files(polygon_id=555, user_id=user.id, db=db)
    assert result["resourceFiles"] == [{"name": "a"}]
    assert result["solutions"] == [{"name": "sol.cpp", "tag": "MA"}]


async def test_route_get_files_empty_results(polygon_api, db, user):
    result = await r.route_get_files(polygon_id=555, user_id=user.id, db=db)
    assert result == {"solutions": []}


async def test_route_view_file_ok(polygon_api, db, user):
    polygon_api.respond("problem.viewFile", "content-here")
    result = await r.route_view_file(
        polygon_id=555, type="source", name="a.cpp", user_id=user.id, db=db
    )
    assert result == {"content": "content-here"}
    assert polygon_api.last().kind == "text"


async def test_route_view_file_polygon_error_is_404(polygon_api, db, user):
    polygon_api.respond("problem.viewFile", PolygonAPIError("name: file not found"))
    with pytest.raises(HTTPException) as exc:
        await r.route_view_file(polygon_id=555, type="source", name="x", user_id=user.id, db=db)
    assert exc.value.status_code == 404
    assert "file not found" in exc.value.detail


async def test_route_view_file_bad_type_is_param_error(polygon_api, db, user):
    with pytest.raises(PolygonParamError):
        await r.route_view_file(polygon_id=555, type="exe", name="x", user_id=user.id, db=db)
    assert polygon_api.calls == []


async def test_route_save_file(polygon_api, db, user):
    body = SaveFileRequest(type="source", name="gen.cpp", content="int main(){}",
                           source_type="cpp.g++17", check_existing=False)
    assert await r.route_save_file(polygon_id=555, body=body, user_id=user.id, db=db) == {
        "ok": True}
    assert polygon_api.last().params == {
        **P, "type": "source", "name": "gen.cpp", "file": "int main(){}",
        "sourceType": "cpp.g++17", "checkExisting": "false",
    }


async def test_route_view_solution_ok_and_404(polygon_api, db, user):
    polygon_api.respond("problem.viewSolution", "int main(){}")
    assert await r.route_view_solution(
        polygon_id=555, name="m.cpp", user_id=user.id, db=db) == {"content": "int main(){}"}

    polygon_api.respond("problem.viewSolution", PolygonAPIError("no such solution"))
    with pytest.raises(HTTPException) as exc:
        await r.route_view_solution(polygon_id=555, name="x", user_id=user.id, db=db)
    assert exc.value.status_code == 404


async def test_route_save_solution(polygon_api, db, user):
    body = SaveSolutionRequest(name="wa.cpp", content="code", tag="WA")
    await r.route_save_solution(polygon_id=555, body=body, user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "name": "wa.cpp", "file": "code", "tag": "WA"}


async def test_route_edit_solution_extra_tags(polygon_api, db, user):
    body = EditSolutionExtraTagsRequest(remove=False, test_group="1", tag="TL")
    await r.route_edit_solution_extra_tags(
        polygon_id=555, name="tl.cpp", body=body, user_id=user.id, db=db
    )
    assert polygon_api.last().params == {
        **P, "name": "tl.cpp", "remove": "false", "testGroup": "1", "tag": "TL"}


@pytest.mark.parametrize("route,body_cls,setter,param", [
    (r.route_set_checker, SetCheckerRequest, "problem.setChecker", "checker"),
    (r.route_set_validator, SetValidatorRequest, "problem.setValidator", "validator"),
    (r.route_set_interactor, SetInteractorRequest, "problem.setInteractor", "interactor"),
])
async def test_route_upload_and_set(polygon_api, db, user, route, body_cls, setter, param):
    body = body_cls(name="x.cpp", content="code")
    assert await route(polygon_id=555, body=body, user_id=user.id, db=db) == {"ok": True}
    assert polygon_api.methods == ["problem.saveFile", setter]
    assert polygon_api.calls[1].params == {**P, param: "x.cpp"}


async def test_route_set_standard_checker_without_upload(polygon_api, db, user):
    body = SetCheckerRequest(name="std::ncmp.cpp")
    assert await r.route_set_checker(polygon_id=555, body=body, user_id=user.id, db=db) == {"ok": True}
    assert polygon_api.methods == ["problem.setChecker"]
    assert polygon_api.last().params == {**P, "checker": "std::ncmp.cpp"}


@pytest.mark.parametrize("route,method,key", [
    (r.route_get_checker, "problem.checker", "checker"),
    (r.route_get_validator, "problem.validator", "validator"),
    (r.route_get_interactor, "problem.interactor", "interactor"),
    (r.route_get_extra_validators, "problem.extraValidators", "extra_validators"),
])
async def test_route_getters(polygon_api, db, user, route, method, key):
    value = ["v2.cpp"] if key == "extra_validators" else "x.cpp"
    polygon_api.respond(method, value)
    assert await route(polygon_id=555, user_id=user.id, db=db) == {key: value}


async def test_route_checker_and_validator_tests(polygon_api, db, user):
    polygon_api.respond("problem.checkerTests", [{"index": 1}])
    polygon_api.respond("problem.validatorTests", [{"index": 2}])
    assert await r.route_get_checker_tests(polygon_id=555, user_id=user.id, db=db) == [
        {"index": 1}]
    assert await r.route_get_validator_tests(polygon_id=555, user_id=user.id, db=db) == [
        {"index": 2}]

    await r.route_save_checker_test(
        polygon_id=555, user_id=user.id, db=db,
        body=SaveCheckerTestRequest(test_index=1, test_input="1", test_output="1",
                                    test_answer="2", test_verdict="WRONG_ANSWER"),
    )
    assert polygon_api.last().params["testVerdict"] == "WRONG_ANSWER"

    await r.route_save_validator_test(
        polygon_id=555, user_id=user.id, db=db,
        body=SaveValidatorTestRequest(test_index=3, test_input="-1", test_verdict="INVALID"),
    )
    assert polygon_api.last().params == {
        **P, "testIndex": "3", "testInput": "-1", "testVerdict": "INVALID"}


async def test_route_script_get_save_clear(polygon_api, db, user):
    polygon_api.respond("problem.script", "gen 1 > $")
    assert await r.route_get_script(
        polygon_id=555, testset="tests", user_id=user.id, db=db) == {"content": "gen 1 > $"}

    await r.route_save_script(polygon_id=555, testset="tests",
                              body=SaveScriptRequest(source="gen 2 > $"),
                              user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "testset": "tests", "source": "gen 2 > $"}

    await r.route_clear_script(polygon_id=555, testset="tests", user_id=user.id, db=db)
    assert polygon_api.last().method == "problem.clearScript"


async def test_route_save_solution_empty_tag_is_skipped(polygon_api, db, user):
    body = SaveSolutionRequest(name="a.cpp", content="x", tag="", source_type="")
    await r.route_save_solution(polygon_id=555, body=body, user_id=user.id, db=db)
    assert polygon_api.last().params == {"problemId": "555", "name": "a.cpp", "file": "x"}
