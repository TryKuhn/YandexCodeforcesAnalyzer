from backend.tests.api_tests.test_base import client


# Basic successful password change
def test_change_password_success():
    client.post(
        "/register",
        json={
            "login": "change_password_success_user",
            "password": "Aa1!aaaa",
            "email": "change_password_success_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_success_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Password changed successfully. Please login again."
    }


# Refresh token does not exist
def test_change_password_invalid_token():
    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": "invalid_refresh_token",
            },
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


# Old password is wrong
def test_change_password_invalid_old_password():
    client.post(
        "/register",
        json={
            "login": "change_password_wrong_old_user",
            "password": "Aa1!aaaa",
            "email": "change_password_wrong_old_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_wrong_old_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "WrongPassword123!",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid old password"}


# New password and confirm password do not match
def test_change_password_confirmation_mismatch():
    client.post(
        "/register",
        json={
            "login": "change_password_mismatch_user",
            "password": "Aa1!aaaa",
            "email": "change_password_mismatch_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_mismatch_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Cc3#cccc",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "New password and confirmation do not match"
    }


# New password is too short
def test_change_password_too_short_new_password():
    client.post(
        "/register",
        json={
            "login": "change_password_short_user",
            "password": "Aa1!aaaa",
            "email": "change_password_short_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_short_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbb",
                "confirm_password": "Bb2@bbb",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Password must be at least 8 characters long"
    }


# Old password should not work after password change
def test_change_password_old_password_is_invalid_after_change():
    client.post(
        "/register",
        json={
            "login": "change_password_old_invalid_user",
            "password": "Aa1!aaaa",
            "email": "change_password_old_invalid_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_old_invalid_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    change_response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    old_login_response = client.post(
        "/login",
        json={
            "login": "change_password_old_invalid_user",
            "password": "Aa1!aaaa",
        },
    )

    assert change_response.status_code == 200
    assert old_login_response.status_code == 401
    assert old_login_response.json() == {"detail": "Invalid login or password"}


# New password should work after password change
def test_change_password_new_password_works_after_change():
    client.post(
        "/register",
        json={
            "login": "change_password_new_valid_user",
            "password": "Aa1!aaaa",
            "email": "change_password_new_valid_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_new_valid_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    change_response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    new_login_response = client.post(
        "/login",
        json={
            "login": "change_password_new_valid_user",
            "password": "Bb2@bbbb",
        },
    )

    assert change_response.status_code == 200
    assert new_login_response.status_code == 200


# All sessions should be closed after password change
def test_change_password_logs_out_all_sessions():
    client.post(
        "/register",
        json={
            "login": "change_password_logout_all_user",
            "password": "Aa1!aaaa",
            "email": "change_password_logout_all_user@example.com",
        },
    )

    login_response_1 = client.post(
        "/login",
        json={
            "login": "change_password_logout_all_user",
            "password": "Aa1!aaaa",
        },
    )

    login_response_2 = client.post(
        "/login",
        json={
            "login": "change_password_logout_all_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token_1 = login_response_1.json()["refresh_token"]
    refresh_token_2 = login_response_2.json()["refresh_token"]

    change_response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
            "token": {
                "refresh_token": refresh_token_1,
            },
        },
    )

    logout_response_1 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token_1,
        },
    )

    logout_response_2 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token_2,
        },
    )

    assert change_response.status_code == 200
    assert logout_response_1.status_code == 400
    assert logout_response_1.json() == {"detail": "Invalid refresh token"}
    assert logout_response_2.status_code == 400
    assert logout_response_2.json() == {"detail": "Invalid refresh token"}


# Missing payload field
def test_change_password_without_payload():
    response = client.post(
        "/change_password",
        json={
            "token": {
                "refresh_token": "some_token",
            },
        },
    )

    assert response.status_code == 422


# Missing token field
def test_change_password_without_token():
    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Bb2@bbbb",
                "confirm_password": "Bb2@bbbb",
            },
        },
    )

    assert response.status_code == 422

# New password has no digit
def test_change_password_without_digit():
    client.post(
        "/register",
        json={
            "login": "change_password_without_digit_user",
            "password": "Aa1!aaaa",
            "email": "change_password_without_digit_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_without_digit_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Aa!aaaaa",
                "confirm_password": "Aa!aaaaa",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain at least one digit"}


# New password has no lowercase latin letter
def test_change_password_without_lowercase_latin_letter():
    client.post(
        "/register",
        json={
            "login": "change_password_without_lowercase_user",
            "password": "Aa1!aaaa",
            "email": "change_password_without_lowercase_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_without_lowercase_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "AA1!AAAA",
                "confirm_password": "AA1!AAAA",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Password must contain at least one lowercase Latin letter"
    }


# New password has no uppercase latin letter
def test_change_password_without_uppercase_latin_letter():
    client.post(
        "/register",
        json={
            "login": "change_password_without_uppercase_user",
            "password": "Aa1!aaaa",
            "email": "change_password_without_uppercase_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_without_uppercase_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "aa1!aaaa",
                "confirm_password": "aa1!aaaa",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Password must contain at least one uppercase Latin letter"
    }


# New password has no special symbol
def test_change_password_without_special_symbol():
    client.post(
        "/register",
        json={
            "login": "change_password_without_special_user",
            "password": "Aa1!aaaa",
            "email": "change_password_without_special_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_without_special_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Aa1aaaaa",
                "confirm_password": "Aa1aaaaa",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Password must contain at least one special symbol"
    }


# New password has only lowercase latin letters
def test_change_password_only_lowercase_latin_letters():
    client.post(
        "/register",
        json={
            "login": "change_password_only_lowercase_user",
            "password": "Aa1!aaaa",
            "email": "change_password_only_lowercase_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_only_lowercase_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "aaabbbccc",
                "confirm_password": "aaabbbccc",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Only lowercase letters!"}


# New password has only uppercase latin letters
def test_change_password_only_uppercase_latin_letters():
    client.post(
        "/register",
        json={
            "login": "change_password_only_uppercase_user",
            "password": "Aa1!aaaa",
            "email": "change_password_only_uppercase_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_only_uppercase_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "AAABBBCCC",
                "confirm_password": "AAABBBCCC",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Only uppercase letters!"}


# New password has cyrillic letters
def test_change_password_with_cyrillic_letters():
    client.post(
        "/register",
        json={
            "login": "change_password_cyrillic_user",
            "password": "Aa1!aaaa",
            "email": "change_password_cyrillic_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "change_password_cyrillic_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/change_password",
        json={
            "payload": {
                "old_password": "Aa1!aaaa",
                "new_password": "Пароль1!",
                "confirm_password": "Пароль1!",
            },
            "token": {
                "refresh_token": refresh_token,
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain only Latin letters"}