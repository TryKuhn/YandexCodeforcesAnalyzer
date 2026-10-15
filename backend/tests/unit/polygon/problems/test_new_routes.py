"""Routes added for the previously unwrapped Polygon methods."""
import pytest

from api.pydantic_schemas.user.polygon_task import (
    AddIssueRequest, CommitRequest, SaveGeneralDescriptionRequest,
    SaveGeneralTutorialRequest, SaveMaterialRequest, SaveNoteRequest,
    SetAccessRequest, UpdateIssueRequest)
from api.user.polygon.client import PolygonAPIError
from api.user.polygon.contests import route_get_contest_problems
from api.user.polygon.problems import issues, materials, meta, working_copy

P = {"problemId": "555"}


async def test_note_get_and_save(polygon_api, db, user):
    polygon_api.respond("problem.note", "wip")
    assert await meta.route_get_note(polygon_id=555, user_id=user.id, db=db) == {"note": "wip"}
    await meta.route_save_note(polygon_id=555, body=SaveNoteRequest(note=""),
                               user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "note": ""}


async def test_general_description_and_tutorial(polygon_api, db, user):
    polygon_api.respond("problem.viewGeneralDescription", "D")
    polygon_api.respond("problem.viewGeneralTutorial", "T")
    assert await meta.route_get_general_description(
        polygon_id=555, user_id=user.id, db=db) == {"description": "D"}
    assert await meta.route_get_general_tutorial(
        polygon_id=555, user_id=user.id, db=db) == {"tutorial": "T"}

    await meta.route_save_general_description(
        polygon_id=555, body=SaveGeneralDescriptionRequest(description="D2"),
        user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "description": "D2"}
    await meta.route_save_general_tutorial(
        polygon_id=555, body=SaveGeneralTutorialRequest(tutorial="T2"),
        user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "tutorial": "T2"}


async def test_accesses(polygon_api, db, user):
    polygon_api.respond("problem.accesses", [{"login": "bob", "accessType": "READ"}])
    assert await meta.route_get_accesses(polygon_id=555, user_id=user.id, db=db) == [
        {"login": "bob", "accessType": "READ"}]
    await meta.route_set_access(polygon_id=555,
                                body=SetAccessRequest(login="bob", access_type="none"),
                                user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "login": "bob", "accessType": "NONE"}


async def test_working_copy_update_discard(polygon_api, db, user):
    await working_copy.route_update_working_copy(polygon_id=555, user_id=user.id, db=db)
    await working_copy.route_discard_working_copy(polygon_id=555, user_id=user.id, db=db)
    assert polygon_api.methods == ["problem.updateWorkingCopy", "problem.discardWorkingCopy"]


async def test_commit_returns_result_and_conflict_is_409(polygon_api, db, user):
    polygon_api.respond("problem.commitChanges", {"committed": True})
    result = await working_copy.route_commit(
        polygon_id=555, body=CommitRequest(message="fix"), user_id=user.id, db=db)
    assert result == {"committed": True}
    assert polygon_api.last().params == {**P, "minorChanges": "true", "message": "fix"}

    polygon_api.respond("problem.commitChanges", {"conflictOccurred": True})
    with pytest.raises(PolygonAPIError) as exc:
        await working_copy.route_commit(polygon_id=555, body=CommitRequest(),
                                        user_id=user.id, db=db)
    assert exc.value.http_status == 409


async def test_materials(polygon_api, db, user):
    polygon_api.respond("problem.materials", [{"name": "pack"}])
    assert await materials.route_get_materials(polygon_id=555, user_id=user.id, db=db) == [
        {"name": "pack"}]

    body = SaveMaterialRequest(publish_strategy="WITH_STATEMENT",
                               items=[{"type": "TEST_INPUTS", "tests": [{"testset": "tests",
                                                                         "all": True}]}])
    await materials.route_save_material(polygon_id=555, name="pack", body=body,
                                        user_id=user.id, db=db)
    params = polygon_api.last().params
    assert params["publishStrategy"] == "WITH_STATEMENT"
    assert params["items"] == '[{"type":"TEST_INPUTS","tests":[{"testset":"tests","all":true}]}]'

    await materials.route_remove_material(polygon_id=555, name="pack", user_id=user.id, db=db)
    assert polygon_api.last().params == {**P, "name": "pack", "remove": "true"}


async def test_cautions_and_issues(polygon_api, db, user):
    polygon_api.respond("problem.cautions", {"common": []})
    polygon_api.respond("problem.issues", [{"id": 1}])
    polygon_api.respond("problem.addIssue", {"id": 2, "status": "OPENED"})
    polygon_api.respond("problem.updateIssue", {"id": 2, "status": "CLOSED"})

    assert await issues.route_get_cautions(polygon_id=555, user_id=user.id, db=db) == {
        "common": []}
    assert await issues.route_get_issues(polygon_id=555, user_id=user.id, db=db) == [{"id": 1}]

    created = await issues.route_add_issue(
        polygon_id=555, body=AddIssueRequest(type="bug", content="broken"),
        user_id=user.id, db=db)
    assert created["status"] == "OPENED"
    assert polygon_api.last().params == {**P, "type": "BUG", "content": "broken"}

    updated = await issues.route_update_issue(
        polygon_id=555, issue_id=2, body=UpdateIssueRequest(status="CLOSED", comment="ok"),
        user_id=user.id, db=db)
    assert updated["status"] == "CLOSED"
    assert polygon_api.last().params == {**P, "issueId": "2", "comment": "ok",
                                         "status": "CLOSED"}


async def test_contest_problems(polygon_api, db, user):
    polygon_api.respond("contest.problems", {"A": {"id": 1}})
    assert await route_get_contest_problems(contest_id=42, user_id=user.id, db=db) == {
        "A": {"id": 1}}
    assert polygon_api.last().params == {"contestId": "42"}
