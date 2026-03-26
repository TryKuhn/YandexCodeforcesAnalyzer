from backend.tests.api_tests.test_base import client

# Basic successful logout
def test_logout_success():
    client.post(
        "/register",
        json={
            "login": "logout_success_user",
            "password": "Aa1!aaaa",
            "email": "logout_success_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "logout_success_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful!"}


# Refresh token does not exist
def test_logout_invalid_refresh_token():
    response = client.post(
        "/logout",
        json={
            "refresh_token": "invalid_refresh_token",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid refresh token"}


# Same refresh token is used again
def test_logout_twice_with_same_refresh_token():
    client.post(
        "/register",
        json={
            "login": "logout_twice_user",
            "password": "Aa1!aaaa",
            "email": "logout_twice_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "logout_twice_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token = login_response.json()["refresh_token"]

    response_1 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    response_2 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert response_1.status_code == 200
    assert response_1.json() == {"message": "Logout successful!"}

    assert response_2.status_code == 400
    assert response_2.json() == {"detail": "Invalid refresh token"}


# Missing refresh token field
def test_logout_without_refresh_token():
    response = client.post(
        "/logout",
        json={},
    )

    assert response.status_code == 422

# User logs in two times and logs out from both sessions
def test_logout_from_two_sessions():
    client.post(
        "/register",
        json={
            "login": "logout_two_sessions_user",
            "password": "Aa1!aaaa",
            "email": "logout_two_sessions_user@example.com",
        },
    )

    login_response_1 = client.post(
        "/login",
        json={
            "login": "logout_two_sessions_user",
            "password": "Aa1!aaaa",
        },
    )

    login_response_2 = client.post(
        "/login",
        json={
            "login": "logout_two_sessions_user",
            "password": "Aa1!aaaa",
        },
    )

    refresh_token_1 = login_response_1.json()["refresh_token"]
    refresh_token_2 = login_response_2.json()["refresh_token"]

    response_1 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token_1,
        },
    )

    response_2 = client.post(
        "/logout",
        json={
            "refresh_token": refresh_token_2,
        },
    )

    assert login_response_1.status_code == 200
    assert login_response_2.status_code == 200
    assert refresh_token_1 != refresh_token_2

    assert response_1.status_code == 200
    assert response_1.json() == {"message": "Logout successful!"}

    assert response_2.status_code == 200
    assert response_2.json() == {"message": "Logout successful!"}

