from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register_and_login(login, password="Aa1!aaaa"):
    client.post(f"{BASE}/register", json={"login": login, "password": password, "email": f"{login}@example.com"})
    r = client.post(f"{BASE}/login", json={"login": login, "password": password})
    return r.json()


def _refresh(refresh_token):
    return client.post(f"{BASE}/refresh", json={"refresh_token": refresh_token})


def _assert_token_response(response):
    data = response.json()
    assert response.status_code == 200
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["token_type"] == "Bearer"


def test_refresh_success():
    tokens = _register_and_login("refresh_success_user")
    assert _refresh(tokens["refresh_token"]).status_code == 200


def test_refresh_returns_correct_json():
    tokens = _register_and_login("refresh_json_user")
    _assert_token_response(_refresh(tokens["refresh_token"]))


def test_refresh_returns_new_refresh_token():
    tokens = _register_and_login("refresh_new_token_user")
    r = _refresh(tokens["refresh_token"])
    assert r.status_code == 200
    assert r.json()["refresh_token"] != tokens["refresh_token"]


def test_refresh_old_token_is_invalid_after_refresh():
    tokens = _register_and_login("refresh_old_token_user")
    old_rt = tokens["refresh_token"]
    r1 = _refresh(old_rt)
    r2 = _refresh(old_rt)
    assert r1.status_code == 200
    assert r2.status_code == 401
    assert r2.json() == {"detail": "Invalid refresh token"}


def test_refresh_new_token_can_be_used_again():
    tokens = _register_and_login("refresh_again_user")
    r1 = _refresh(tokens["refresh_token"])
    r2 = _refresh(r1.json()["refresh_token"])
    assert r1.status_code == 200
    assert r2.status_code == 200
    _assert_token_response(r2)


def test_refresh_invalid_refresh_token():
    r = _refresh("invalid_refresh_token")
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid refresh token"}


def test_refresh_without_refresh_token():
    r = client.post(f"{BASE}/refresh", json={})
    assert r.status_code == 422
