from tests.api_tests.test_base import client

AUTH = "/api/auth"
CF = "/api/codeforces"


def _register_and_login(login):
    client.post(f"{AUTH}/register", json={"login": login, "password": "Aa1!aaaa", "email": f"{login}@example.com"})
    r = client.post(f"{AUTH}/login", json={"login": login, "password": "Aa1!aaaa"})
    return r.json()["access_token"]


def test_unlink_codeforces_success():
    token = _register_and_login("cf_unlink_user_ok")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(f"{CF}/link", json={"api_key": "fake_key", "api_secret": "fake_secret"}, headers=headers)
    r = client.post(f"{CF}/unlink", headers=headers)

    assert r.status_code == 200
    assert r.json() == {"message": "Codeforces account successfully unlinked"}


def test_unlink_codeforces_without_auth():
    r = client.post(f"{CF}/unlink")
    assert r.status_code == 401


def test_unlink_codeforces_idempotent():
    token = _register_and_login("cf_unlink_idempotent_user")
    headers = {"Authorization": f"Bearer {token}"}

    client.post(f"{CF}/link", json={"api_key": "fake_key", "api_secret": "fake_secret"}, headers=headers)
    r1 = client.post(f"{CF}/unlink", headers=headers)
    r2 = client.post(f"{CF}/unlink", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json() == {"message": "Codeforces account successfully unlinked"}
