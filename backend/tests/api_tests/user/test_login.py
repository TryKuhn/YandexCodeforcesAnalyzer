from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register(login, password="Aa1!aaaa"):
    client.post(f"{BASE}/register", json={"login": login, "password": password, "email": f"{login}@example.com"})


def _login(login, password="Aa1!aaaa"):
    return client.post(f"{BASE}/login", json={"login": login, "password": password})


def _assert_token_response(response):
    data = response.json()
    assert response.status_code == 200
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["access_token"] != ""
    assert data["refresh_token"] != ""
    assert data["access_token"] != data["refresh_token"]


def test_login_success():
    _register("login_success_user")
    assert _login("login_success_user").status_code == 200


def test_login_user_not_found():
    r = _login("missing_user")
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid login or password"}


def test_login_wrong_password():
    _register("wrong_password_user")
    r = _login("wrong_password_user", password="WrongPassword123!")
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid login or password"}


def test_login_returns_correct_json():
    _register("json_user")
    _assert_token_response(_login("json_user"))


def test_login_twice_returns_correct_json():
    _register("login_twice_user")
    r1 = _login("login_twice_user")
    r2 = _login("login_twice_user")
    _assert_token_response(r1)
    _assert_token_response(r2)
    assert r1.json()["refresh_token"] != r2.json()["refresh_token"]


def test_login_another_user_returns_correct_json():
    _register("another_login_user", password="Bb2@bbbb")
    _assert_token_response(_login("another_login_user", password="Bb2@bbbb"))


def test_login_two_users_return_correct_json():
    _register("first_json_user")
    _register("second_json_user", password="Bb2@bbbb")
    r1 = _login("first_json_user")
    r2 = _login("second_json_user", password="Bb2@bbbb")
    _assert_token_response(r1)
    _assert_token_response(r2)
    assert r1.json()["access_token"] != r2.json()["access_token"]
    assert r1.json()["refresh_token"] != r2.json()["refresh_token"]


def test_login_without_login():
    r = client.post(f"{BASE}/login", json={"password": "Aa1!aaaa"})
    assert r.status_code == 422


def test_login_without_password():
    r = client.post(f"{BASE}/login", json={"login": "some_user"})
    assert r.status_code == 422
