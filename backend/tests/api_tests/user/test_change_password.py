from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register_and_login(login, password="Aa1!aaaa"):
    client.post(
        f"{BASE}/register",
        json={"login": login, "password": password, "email": f"{login}@example.com"},
    )
    r = client.post(f"{BASE}/login", json={"login": login, "password": password})
    return r.json()


def _change_password(access_token, old_password, new_password, confirm_password=None):
    return client.post(
        f"{BASE}/change_password",
        json={
            "old_password": old_password,
            "new_password": new_password,
            "confirm_password": confirm_password or new_password,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )


def test_change_password_success():
    tokens = _register_and_login("cp_success_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbbb")
    assert r.status_code == 200
    assert r.json() == {"message": "Password changed successfully. Please login again."}


def test_change_password_invalid_token():
    r = _change_password("totally.invalid.token", "Aa1!aaaa", "Bb2@bbbb")
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid token"}


def test_change_password_invalid_old_password():
    tokens = _register_and_login("cp_wrong_old_user")
    r = _change_password(tokens["access_token"], "WrongPassword123!", "Bb2@bbbb")
    assert r.status_code == 400
    assert r.json() == {"detail": "Invalid old password"}


def test_change_password_confirmation_mismatch():
    tokens = _register_and_login("cp_mismatch_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbbb", "Cc3#cccc")
    assert r.status_code == 400
    assert r.json() == {"detail": "New password and confirmation do not match"}


def test_change_password_too_short_new_password():
    tokens = _register_and_login("cp_short_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbb")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must be at least 8 characters long"}


def test_change_password_old_password_is_invalid_after_change():
    tokens = _register_and_login("cp_old_invalid_user")
    _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbbb")
    r = client.post(
        f"{BASE}/login", json={"login": "cp_old_invalid_user", "password": "Aa1!aaaa"}
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "Invalid login or password"}


def test_change_password_new_password_works_after_change():
    tokens = _register_and_login("cp_new_valid_user")
    _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbbb")
    r = client.post(
        f"{BASE}/login", json={"login": "cp_new_valid_user", "password": "Bb2@bbbb"}
    )
    assert r.status_code == 200


def test_change_password_logs_out_all_sessions():
    tokens = _register_and_login("cp_logout_all_user")
    rt1 = tokens["refresh_token"]
    rt2 = client.post(
        f"{BASE}/login", json={"login": "cp_logout_all_user", "password": "Aa1!aaaa"}
    ).json()["refresh_token"]

    _change_password(tokens["access_token"], "Aa1!aaaa", "Bb2@bbbb")

    r1 = client.post(f"{BASE}/logout", json={"refresh_token": rt1})
    r2 = client.post(f"{BASE}/logout", json={"refresh_token": rt2})
    assert r1.status_code == 400
    assert r1.json() == {"detail": "Invalid refresh token"}
    assert r2.status_code == 400
    assert r2.json() == {"detail": "Invalid refresh token"}


def test_change_password_without_payload():
    r = client.post(
        f"{BASE}/change_password", json={}, headers={"Authorization": "Bearer dummy"}
    )
    assert r.status_code in (401, 422)


def test_change_password_without_digit():
    tokens = _register_and_login("cp_nodigit_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Aa!aaaaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one digit"}


def test_change_password_without_lowercase():
    tokens = _register_and_login("cp_nolower_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "AA1!AAAA")
    assert r.status_code == 400
    assert r.json() == {
        "detail": "Password must contain at least one lowercase Latin letter"
    }


def test_change_password_without_uppercase():
    tokens = _register_and_login("cp_noupper_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "aa1!aaaa")
    assert r.status_code == 400
    assert r.json() == {
        "detail": "Password must contain at least one uppercase Latin letter"
    }


def test_change_password_without_special_symbol():
    tokens = _register_and_login("cp_nospecial_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Aa1aaaaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one special symbol"}


def test_change_password_only_lowercase():
    tokens = _register_and_login("cp_onlylower_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "aaabbbccc")
    assert r.status_code == 400
    assert r.json() == {"detail": "Only lowercase letters!"}


def test_change_password_only_uppercase():
    tokens = _register_and_login("cp_onlyupper_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "AAABBBCCC")
    assert r.status_code == 400
    assert r.json() == {"detail": "Only uppercase letters!"}


def test_change_password_with_cyrillic_letters():
    tokens = _register_and_login("cp_cyrillic_user")
    r = _change_password(tokens["access_token"], "Aa1!aaaa", "Пароль1!")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain only Latin letters"}
