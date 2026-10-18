"""Wrapper behaviour beyond the raw request: return values, validation, composites."""
import pytest

from api.user.polygon import methods as m
from api.user.polygon.client import PolygonAPIError, PolygonParamError


# --- return values -----------------------------------------------------------
async def test_create_problem_returns_int_id(polygon_api, db, user):
    polygon_api.respond("problem.create", {"id": "321", "name": "x"})
    assert await m.create_problem("x", user.id, db) == 321


async def test_create_problem_without_id_raises(polygon_api, db, user):
    polygon_api.respond("problem.create", {})
    with pytest.raises(PolygonAPIError, match="id"):
        await m.create_problem("x", user.id, db)


@pytest.mark.parametrize("fn,method", [
    (lambda u, d: m.get_tests(1, "tests", u, d), "problem.tests"),
    (lambda u, d: m.get_solutions(1, u, d), "problem.solutions"),
    (lambda u, d: m.get_packages(1, u, d), "problem.packages"),
    (lambda u, d: m.view_tags(1, u, d), "problem.viewTags"),
    (lambda u, d: m.list_problems(u, d), "problems.list"),
    (lambda u, d: m.get_issues(1, u, d), "problem.issues"),
])
async def test_list_methods_normalize_missing_result_to_empty_list(
    polygon_api, db, user, fn, method
):
    polygon_api.respond(method, None)
    assert await fn(user.id, db) == []


async def test_text_getters_never_return_none(polygon_api, db, user):
    for method in ("problem.note", "problem.checker", "problem.validator",
                   "problem.interactor", "problem.viewGeneralDescription"):
        polygon_api.respond(method, None)
    assert await m.get_note(1, user.id, db) == ""
    assert await m.get_checker(1, user.id, db) == ""
    assert await m.get_validator(1, user.id, db) == ""
    assert await m.get_interactor(1, user.id, db) == ""
    assert await m.view_general_description(1, user.id, db) == ""


async def test_commit_conflict_raises_409(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {"committed": False, "conflictOccurred": True})
    with pytest.raises(PolygonAPIError) as exc:
        await m.commit_changes(1, user.id, db)
    assert exc.value.http_status == 409
    assert exc.value.result["conflictOccurred"] is True


async def test_commit_returns_commit_result(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {"committed": True, "conflictOccurred": False})
    assert (await m.commit_changes(1, user.id, db))["committed"] is True


async def test_commit_empty_message_not_sent(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {})
    await m.commit_changes(1, user.id, db, message="")
    assert "message" not in polygon_api.last().params


# --- composites ----------------------------------------------------------------
@pytest.mark.parametrize("fn,setter,param", [
    (m.upload_checker, "problem.setChecker", "checker"),
    (m.upload_validator, "problem.setValidator", "validator"),
    (m.upload_interactor, "problem.setInteractor", "interactor"),
])
async def test_upload_saves_source_then_sets(polygon_api, db, user, fn, setter, param):
    await fn(5, "x.cpp", "code", user.id, db)
    assert polygon_api.methods == ["problem.saveFile", setter]
    assert polygon_api.calls[0].params == {
        "problemId": "5", "type": "source", "name": "x.cpp", "file": "code"
    }
    assert polygon_api.calls[1].params == {"problemId": "5", param: "x.cpp"}


# --- validation (nothing is sent) ----------------------------------------------
@pytest.mark.parametrize("call,match", [
    (lambda u, d: m.save_test_group(1, "tests", "1", u, d, points_policy="complete"),
     "pointsPolicy"),
    (lambda u, d: m.save_test_group(1, "tests", "1", u, d, feedback_policy="first"),
     "feedbackPolicy"),
    (lambda u, d: m.save_solution(1, "a.cpp", "x", u, d, tag="AC"), "tag"),
    (lambda u, d: m.edit_solution_extra_tags(1, "a", False, u, d, testset="t", tag="MA"),
     "tag"),
    (lambda u, d: m.edit_solution_extra_tags(1, "a", False, u, d, tag="OK"), "ровно один"),
    (lambda u, d: m.edit_solution_extra_tags(
        1, "a", False, u, d, testset="t", test_group="g", tag="OK"), "ровно один"),
    (lambda u, d: m.view_file(1, "binary", "a", u, d), "type"),
    (lambda u, d: m.save_file(1, "source", "a", "x", u, d, for_types="cpp.*",
                              stages="COMPILE", assets="SOLUTION"), "resource"),
    (lambda u, d: m.save_file(1, "resource", "a", "x", u, d, for_types="cpp.*"), "вместе"),
    (lambda u, d: m.delete_tests(1, "tests", [], u, d), "пуст"),
    (lambda u, d: m.set_test_group(1, "tests", "1", [], u, d), "пуст"),
    (lambda u, d: m.update_info(1, u, d, time_limit=1001), "timeLimit"),
    (lambda u, d: m.update_info(1, u, d, time_limit=100), "timeLimit"),
    (lambda u, d: m.update_info(1, u, d, memory_limit=2048), "memoryLimit"),
    (lambda u, d: m.save_note(1, "x" * 51, u, d), "50"),
    (lambda u, d: m.save_statement(1, "russian", u, d, name="a\nb"), "одну строку"),
    (lambda u, d: m.set_access(1, "@group", "READ", u, d), "групп"),
    (lambda u, d: m.set_access(1, "bob", "OWNER", u, d), "accessType"),
    (lambda u, d: m.save_validator_test(1, 1, u, d, test_verdict="OK"), "testVerdict"),
    (lambda u, d: m.save_checker_test(1, 1, u, d, test_verdict="WA"), "testVerdict"),
    (lambda u, d: m.download_package(1, 2, u, d, package_type="zip"), "type"),
    (lambda u, d: m.save_material(1, "", "NONE", [{"type": "SOLUTIONS"}], u, d), "name"),
    (lambda u, d: m.save_material(1, "a", "NONE", [], u, d), "items"),
    (lambda u, d: m.save_material(1, "a", "NONE", [{"type": "X"}], u, d), "items"),
    (lambda u, d: m.save_material(1, "a", "PUBLIC", [{"type": "SOLUTIONS"}], u, d),
     "publishStrategy"),
    (lambda u, d: m.add_issue(1, "BUG", "", u, d), "content"),
    (lambda u, d: m.add_issue(1, "QUESTION", "x", u, d), "type"),
    (lambda u, d: m.update_issue(1, 2, u, d), "изменение"),
    (lambda u, d: m.update_issue(1, 2, u, d, comment="   "), "изменение"),
    (lambda u, d: m.update_issue(1, 2, u, d, status="OPENED"), "status"),
    (lambda u, d: m.save_test(1, "tests", 1, "x", u, d, test_points=-1), "testPoints"),
    (lambda u, d: m.edit_solution_extra_tags(1, "a", False, u, d, testset="t"), "tag"),
])
async def test_invalid_params_rejected_before_request(polygon_api, db, user, call, match):
    with pytest.raises(PolygonParamError, match=match) as exc:
        await call(user.id, db)
    assert exc.value.http_status == 422
    assert polygon_api.calls == []


async def test_save_file_empty_for_types_removes_advanced_props(polygon_api, db, user):
    await m.save_file(1, "resource", "a.h", None, user.id, db, for_types="")
    assert polygon_api.last().params == {
        "problemId": "1", "type": "resource", "name": "a.h", "forTypes": ""
    }


async def test_update_issue_status_change_without_comment_is_ok(polygon_api, db, user):
    polygon_api.respond("problem.updateIssue", {"id": 2})
    assert await m.update_issue(1, 2, user.id, db, status="REOPENED") == {"id": 2}


async def test_missing_credentials_is_401_and_nothing_sent(polygon_api, db, user):
    from fastapi import HTTPException

    user.polygon_api_secret = None
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await m.get_info(1, user.id, db)
    assert exc.value.status_code == 401
    assert polygon_api.calls == []


async def test_save_material_sends_canonical_item_types(polygon_api, db, user):
    await m.save_material(1, "p", "none", [{"type": "test_inputs", "tests": []}], user.id, db)
    assert polygon_api.last().params["items"] == '[{"type":"TEST_INPUTS","tests":[]}]'


async def test_save_test_group_accepts_comma_string_dependencies(polygon_api, db, user):
    await m.save_test_group(1, "tests", "3", user.id, db, dependencies="1,2")
    assert polygon_api.last().params["dependencies"] == "1,2"
