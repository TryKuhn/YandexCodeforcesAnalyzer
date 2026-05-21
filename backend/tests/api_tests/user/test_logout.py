from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register_and_login(login, password="Aa1!aaaa"):
    client.post(
        f"{BASE}/register",
        json={"login": login, "password": password, "email": f"{login}@example.com"},
    )
    r = client.post(f"{BASE}/login", json={"login": login, "password": password})
    return r.json()


def _logout(refresh_token):
    return client.post(f"{BASE}/logout", json={"refresh_token": refresh_token})


def test_logout_success():
    tokens = _register_and_login("logout_success_user")
    r = _logout(tokens["refresh_token"])
    assert r.status_code == 200
    assert r.json() == {"message": "Logout successful!"}


def test_logout_invalid_refresh_token():
    r = _logout("invalid_refresh_token")
    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid refresh token"}


def test_logout_twice_with_same_refresh_token():
    tokens = _register_and_login("logout_twice_user")
    rt = tokens["refresh_token"]
    r1 = _logout(rt)
    r2 = _logout(rt)
    assert r1.status_code == 200
    assert r1.json() == {"message": "Logout successful!"}
    assert r2.status_code == 400
    assert r2.json() == {"detail": "Invalid refresh token"}


def test_logout_without_refresh_token():
    r = client.post(f"{BASE}/logout", json={})
    assert r.status_code == 422


def test_logout_from_two_sessions():
    _register_and_login("logout_two_sessions_user")
    rt1 = client.post(
        f"{BASE}/login",
        json={"login": "logout_two_sessions_user", "password": "Aa1!aaaa"},
    ).json()["refresh_token"]
    rt2 = client.post(
        f"{BASE}/login",
        json={"login": "logout_two_sessions_user", "password": "Aa1!aaaa"},
    ).json()["refresh_token"]
    assert rt1 != rt2
    r1 = _logout(rt1)
    r2 = _logout(rt2)
    assert r1.status_code == 200
    assert r1.json() == {"message": "Logout successful!"}
    assert r2.status_code == 200
    assert r2.json() == {"message": "Logout successful!"}
