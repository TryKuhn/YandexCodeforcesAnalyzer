import api.user.polygon.files.test.post.save_test as mod
from api.user.polygon.files.test.post.save_test import save_test


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap.setdefault("calls", []).append((method_name, dict(params)))
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_save_test_str_input_encoded(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_test(5, "tests", 3, "5 6 7", user.id, db)
    assert cap["method"] == "problem.saveTest"
    assert cap["params"]["problemId"] == "5"
    assert cap["params"]["testset"] == "tests"
    assert cap["params"]["testIndex"] == "3"
    assert cap["params"]["testInput"] == b"5 6 7"


async def test_save_test_bytes_passthrough(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_test(5, "tests", 3, b"\x00\x01", user.id, db)
    assert cap["params"]["testInput"] == b"\x00\x01"


async def test_save_test_none_input_omitted(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_test(5, "tests", 3, None, user.id, db)
    assert "testInput" not in cap["params"]


async def test_save_test_all_optionals(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)
    await save_test(
        5,
        "tests",
        3,
        "x",
        user.id,
        db,
        check_existing=False,
        test_group="g1",
        test_points=1.5,
        test_description="desc",
        test_use_in_statements=True,
        test_input_for_statements="in",
        test_output_for_statements="out",
        verify_input_output_for_statements=False,
    )
    p = cap["params"]
    assert p["checkExisting"] == "false"
    assert p["testGroup"] == "g1"
    assert p["testPoints"] == "1.5"
    assert p["testDescription"] == "desc"
    assert p["testUseInStatements"] == "true"
    assert p["testInputForStatements"] == "in"
    assert p["testOutputForStatements"] == "out"
    assert p["verifyInputOutputForStatements"] == "false"
