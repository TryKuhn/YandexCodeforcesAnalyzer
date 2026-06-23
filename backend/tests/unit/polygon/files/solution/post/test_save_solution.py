import api.user.polygon.files.solution.post.save_solution as mod
from api.user.polygon.files.solution.post.save_solution import save_solution


def _patch(monkeypatch, user, ret={"ok": True}):
    cap = {}

    async def fake_get_user(user_id, db):
        cap["user_id"] = user_id
        return user

    async def fake_polygon_call(method_name, params, u):
        cap["method"] = method_name
        cap["params"] = params
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)
    return cap


async def test_save_solution_base_only(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await save_solution(10, "sol.cpp", "int main(){}", None, user.id, db)

    assert cap["method"] == "problem.saveSolution"
    assert cap["params"] == {
        "problemId": "10",
        "name": "sol.cpp",
        "file": "int main(){}",
    }
    assert "tag" not in cap["params"]
    assert "sourceType" not in cap["params"]
    assert "checkExisting" not in cap["params"]


async def test_save_solution_all_optionals(monkeypatch, db, user):
    cap = _patch(monkeypatch, user)

    await save_solution(
        10,
        "sol.cpp",
        "int main(){}",
        "main",
        user.id,
        db,
        source_type="cpp.g++17",
        check_existing=True,
    )

    params = cap["params"]
    assert params["problemId"] == "10"
    assert params["name"] == "sol.cpp"
    assert params["file"] == "int main(){}"
    assert params["tag"] == "main"
    assert params["sourceType"] == "cpp.g++17"
    assert params["checkExisting"] == "true"
