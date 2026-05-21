from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register_and_login(login, password="Aa1!aaaa"):
    client.post(
        f"{BASE}/register",
        json={"login": login, "password": password, "email": f"{login}@example.com"},
    )
    r = client.post(f"{BASE}/login", json={"login": login, "password": password})
    return r.json()


def _logout_all(refresh_token):
    return client.post(f"{BASE}/logout_all", json={"refresh_token": refresh_token})


def _logout(refresh_token):
    return client.post(f"{BASE}/logout", json={"refresh_token": refresh_token})


def test_logout_all_success():
    tokens = _register_and_login("logout_all_success_user")
    r = _logout_all(tokens["refresh_token"])
    assert r.status_code == 200
    assert r.json() == {"message": "Logout all successful!"}


def test_logout_all_invalid_refresh_token():
    r = _logout_all("invalid_refresh_token")
    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid refresh token"}


def test_logout_all_removes_all_user_sessions():
    _register_and_login("logout_all_two_sessions_user")
    rt1 = client.post(
        f"{BASE}/login",
        json={"login": "logout_all_two_sessions_user", "password": "Aa1!aaaa"},
    ).json()["refresh_token"]
    rt2 = client.post(
        f"{BASE}/login",
        json={"login": "logout_all_two_sessions_user", "password": "Aa1!aaaa"},
    ).json()["refresh_token"]

    r = _logout_all(rt1)
    assert r.status_code == 200
    assert r.json() == {"message": "Logout all successful!"}

    assert _logout(rt1).status_code == 400
    assert _logout(rt2).status_code == 400


def test_logout_all_does_not_affect_another_user():
    _register_and_login("first_logout_all_user")
    tokens2 = _register_and_login("second_logout_all_user", password="Bb2@bbbb")
    rt1a = client.post(
        f"{BASE}/login", json={"login": "first_logout_all_user", "password": "Aa1!aaaa"}
    ).json()["refresh_token"]
    rt1b = client.post(
        f"{BASE}/login", json={"login": "first_logout_all_user", "password": "Aa1!aaaa"}
    ).json()["refresh_token"]

    r = _logout_all(rt1a)
    assert r.status_code == 200

    assert _logout(rt1a).status_code == 400
    assert _logout(rt1b).status_code == 400

    # Second user unaffected
    r2 = _logout(tokens2["refresh_token"])
    assert r2.status_code == 200
    assert r2.json() == {"message": "Logout successful!"}


def test_logout_all_twice_with_same_refresh_token():
    tokens = _register_and_login("logout_all_twice_user")
    rt = tokens["refresh_token"]
    r1 = _logout_all(rt)
    r2 = _logout_all(rt)
    assert r1.status_code == 200
    assert r1.json() == {"message": "Logout all successful!"}
    assert r2.status_code == 400
    assert r2.json() == {"detail": "Invalid refresh token"}


def test_logout_all_without_refresh_token():
    r = client.post(f"{BASE}/logout_all", json={})
    assert r.status_code == 422
