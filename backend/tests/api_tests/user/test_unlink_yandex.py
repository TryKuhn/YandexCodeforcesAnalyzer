from tests.api_tests.test_base import client

AUTH = "/api/auth"
YANDEX = "/api/yandex"


def _register_and_login(login):
    client.post(f"{AUTH}/register", json={"login": login, "password": "Aa1!aaaa", "email": f"{login}@example.com"})
    r = client.post(f"{AUTH}/login", json={"login": login, "password": "Aa1!aaaa"})
    return r.json()["access_token"]


def test_unlink_yandex_success():
    token = _register_and_login("yandex_unlink_user_ok")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(f"{YANDEX}/logout", headers=headers)

    assert r.status_code == 200
    assert r.json() == {"message": "Yandex account logged out"}


def test_unlink_yandex_without_auth():
    r = client.post(f"{YANDEX}/logout")
    assert r.status_code == 401


def test_unlink_yandex_idempotent():
    token = _register_and_login("yandex_unlink_idempotent_user")
    headers = {"Authorization": f"Bearer {token}"}

    r1 = client.post(f"{YANDEX}/logout", headers=headers)
    r2 = client.post(f"{YANDEX}/logout", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
