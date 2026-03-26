from backend.tests.api_tests.test_base import client


# Basic successful logout all
def test_logout_all_success():
    client.post(
        "/register",
        json={
            "login": "logout_all_success_user",
            "password": "Aa1!aaaa",
            "email": "logout_all_success_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "logout_all_success_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/logout_all",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Logout all successful!"}


# Refresh token does not exist
def test_logout_all_invalid_refresh_token():
    response = client.post(
        "/logout_all",
        json={
            "refresh_token": "invalid_refresh_token",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid refresh token"}


# User logs in two times and logs out from all sessions
def test_logout_all_removes_all_user_sessions():
    client.post(
        "/register",
        json={
            "login": "logout_all_two_sessions_user",
            "password": "Aa1!aaaa",
            "email": "logout_all_two_sessions_user@example.com",
        },
    )

    login_response_1 = client.post(
        "/login",
        json={
            "login": "logout_all_two_sessions_user",
            "password": "Aa1!aaaa",
        },
    )

    login_response_2 = client.post(
        "/login",
        json={
            "login": "logout_all_two_sessions_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token_1 = login_response_1.json()["refresh_token"]
    refresh_token_2 = login_response_2.json()["refresh_token"]

    logout_all_response = client.post(
        "/logout_all",
        json={
            "refresh_token": refresh_token_1,
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

    assert logout_all_response.status_code == 200
    assert logout_all_response.json() == {"message": "Logout all successful!"}

    assert logout_response_1.status_code == 400
    assert logout_response_1.json() == {"detail": "Invalid refresh token"}

    assert logout_response_2.status_code == 400
    assert logout_response_2.json() == {"detail": "Invalid refresh token"}


# Logout all should not affect another user
def test_logout_all_does_not_affect_another_user():
    client.post(
        "/register",
        json={
            "login": "first_logout_all_user",
            "password": "Aa1!aaaa",
            "email": "first_logout_all_user@example.com",
        },
    )

    client.post(
        "/register",
        json={
            "login": "second_logout_all_user",
            "password": "Bb2@bbbb",
            "email": "second_logout_all_user@example.com",
        },
    )

    first_login_response_1 = client.post(
        "/login",
        json={
            "login": "first_logout_all_user",
            "password": "Aa1!aaaa",
        },
    )

    first_login_response_2 = client.post(
        "/login",
        json={
            "login": "first_logout_all_user",
            "password": "Aa1!aaaa",
        },
    )

    second_login_response = client.post(
        "/login",
        json={
            "login": "second_logout_all_user",
            "password": "Bb2@bbbb",
        },
    )

    first_refresh_token_1 = first_login_response_1.json()["refresh_token"]
    first_refresh_token_2 = first_login_response_2.json()["refresh_token"]
    second_refresh_token = second_login_response.json()["refresh_token"]

    logout_all_response = client.post(
        "/logout_all",
        json={
            "refresh_token": first_refresh_token_1,
        },
    )

    first_logout_response_1 = client.post(
        "/logout",
        json={
            "refresh_token": first_refresh_token_1,
        },
    )

    first_logout_response_2 = client.post(
        "/logout",
        json={
            "refresh_token": first_refresh_token_2,
        },
    )

    second_logout_response = client.post(
        "/logout",
        json={
            "refresh_token": second_refresh_token,
        },
    )

    assert logout_all_response.status_code == 200
    assert logout_all_response.json() == {"message": "Logout all successful!"}

    assert first_logout_response_1.status_code == 400
    assert first_logout_response_1.json() == {"detail": "Invalid refresh token"}

    assert first_logout_response_2.status_code == 400
    assert first_logout_response_2.json() == {"detail": "Invalid refresh token"}

    assert second_logout_response.status_code == 200
    assert second_logout_response.json() == {"message": "Logout successful!"}


# Same refresh token is used again after logout all
def test_logout_all_twice_with_same_refresh_token():
    client.post(
        "/register",
        json={
            "login": "logout_all_twice_user",
            "password": "Aa1!aaaa",
            "email": "logout_all_twice_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "logout_all_twice_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response_1 = client.post(
        "/logout_all",
        json={
            "refresh_token": refresh_token,
        },
    )

    response_2 = client.post(
        "/logout_all",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response_1.status_code == 200
    assert response_1.json() == {"message": "Logout all successful!"}

    assert response_2.status_code == 400
    assert response_2.json() == {"detail": "Invalid refresh token"}


# Missing refresh token field
def test_logout_all_without_refresh_token():
    response = client.post(
        "/logout_all",
        json={},
    )

    assert response.status_code == 422