"""Unit tests for api/user/polygon/problems/tests.py route handlers."""
import pytest
from pydantic import ValidationError

from api.pydantic_schemas.user.polygon_task import (SaveTestRequest,
                                                    SetTestGroupRequest,
                                                    TestIndicesRequest,
                                                    UpdateTestRequest)
from api.user.polygon.client import PolygonAPIError
from api.user.polygon.problems import tests as r

T = {"problemId": "555", "testset": "tests"}


async def test_route_get_tests(polygon_api, db, user):
    polygon_api.respond("problem.tests", [{"index": 1}])
    result = await r.route_get_tests(polygon_id=555, testset="tests", no_inputs=True,
                                     user_id=user.id, db=db)
    assert result == [{"index": 1}]
    assert polygon_api.last().params == {**T, "noInputs": "true"}


async def test_route_preview_tests(polygon_api, db, user):
    polygon_api.respond("problem.previewTests", [{"testIndex": 1, "input": "1"}])
    assert await r.route_preview_tests(polygon_id=555, testset="tests",
                                       user_id=user.id, db=db) == [{"testIndex": 1, "input": "1"}]


async def test_route_get_test_input_and_answer(polygon_api, db, user):
    polygon_api.respond("problem.testInput", "1 2")
    polygon_api.respond("problem.testAnswer", "3")
    assert await r.route_get_test_input(polygon_id=555, testset="tests", index=4,
                                        user_id=user.id, db=db) == {"content": "1 2"}
    assert await r.route_get_test_answer(polygon_id=555, testset="tests", index=4,
                                         user_id=user.id, db=db) == {"content": "3"}
    assert polygon_api.last().params == {**T, "testIndex": "4"}


async def test_route_get_test_preview_truncates(polygon_api, db, user):
    polygon_api.respond("problem.testInput", "x" * 10)
    polygon_api.respond("problem.testAnswer", "y")
    result = await r.route_get_test_preview(polygon_id=555, testset="tests", index=1, limit=4,
                                            user_id=user.id, db=db)
    assert result == {"input": "xxxx", "output": "y",
                      "input_truncated": True, "output_truncated": False}


async def test_route_save_test_passes_str_input(polygon_api, db, user):
    body = UpdateTestRequest(test_input="5 6")
    await r.route_save_test(polygon_id=555, testset="tests", index=2, body=body,
                            user_id=user.id, db=db)
    assert polygon_api.last().params == {
        **T, "testIndex": "2", "testInput": "5 6", "checkExisting": "false"}


async def test_route_create_or_update_test_full_options(polygon_api, db, user):
    body = SaveTestRequest(test_index=3, test_input="1", test_group="1", test_points=10,
                           test_use_in_statements=True)
    await r.route_create_or_update_test(polygon_id=555, testset="tests", body=body,
                                        user_id=user.id, db=db)
    assert polygon_api.last().params == {
        **T, "testIndex": "3", "testInput": "1", "testGroup": "1", "testPoints": "10.0",
        "testUseInStatements": "true",
    }


async def test_route_delete_tests(polygon_api, db, user):
    await r.route_delete_tests(polygon_id=555, testset="tests",
                               body=TestIndicesRequest(test_indices=[4, 5]),
                               user_id=user.id, db=db)
    assert polygon_api.last().params == {**T, "testIndices": "4,5"}


async def test_route_delete_tests_failure_carries_details(polygon_api, db, user):
    failures = {"failures": [{"index": 4, "reason": "FREEMARKER_SCRIPT_TEST"}]}
    polygon_api.respond("problem.deleteTest", PolygonAPIError("refused", result=failures))
    with pytest.raises(PolygonAPIError) as exc:
        await r.route_delete_tests(polygon_id=555, testset="tests",
                                   body=TestIndicesRequest(test_indices=[4]),
                                   user_id=user.id, db=db)
    assert exc.value.result == failures


def test_test_indices_must_not_be_empty():
    with pytest.raises(ValidationError):
        TestIndicesRequest(test_indices=[])


async def test_route_set_test_group(polygon_api, db, user):
    await r.route_set_test_group(polygon_id=555, testset="tests",
                                 body=SetTestGroupRequest(test_group="2", test_indices=[6, 7]),
                                 user_id=user.id, db=db)
    assert polygon_api.last().params == {**T, "testGroup": "2", "testIndices": "6,7"}
