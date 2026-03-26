from backend.tests.api_tests.test_base import client


def assert_refresh_response_json(response):
    data = response.json()

    assert response.status_code == 200
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"


# Basic successful refresh
def test_refresh_success():
    client.post(
        "/register",
        json={
            "login": "refresh_success_user",
            "password": "Aa1!aaaa",
            "email": "refresh_success_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "refresh_success_user",
            "password": "Aa1!aaaa",
        },
    )

    old_refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert response.status_code == 200


# Check full json after refresh
def test_refresh_returns_correct_json():
    client.post(
        "/register",
        json={
            "login": "refresh_json_user",
            "password": "Aa1!aaaa",
            "email": "refresh_json_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "refresh_json_user",
            "password": "Aa1!aaaa",
        },
    )

    old_refresh_token = login_response.json()["refresh_token"]

    response = client.post(
        "/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert_refresh_response_json(response)


# New refresh token should be different from old one
def test_refresh_returns_new_refresh_token():
    client.post(
        "/register",
        json={
            "login": "refresh_new_token_user",
            "password": "Aa1!aaaa",
            "email": "refresh_new_token_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "refresh_new_token_user",
            "password": "Aa1!aaaa",
        },
    )

    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    new_refresh_token = refresh_response.json()["refresh_token"]

    assert refresh_response.status_code == 200
    assert new_refresh_token != old_refresh_token


# Old refresh token should not work after refresh
def test_refresh_old_token_is_invalid_after_refresh():
    client.post(
        "/register",
        json={
            "login": "refresh_old_token_user",
            "password": "Aa1!aaaa",
            "email": "refresh_old_token_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "refresh_old_token_user",
            "password": "Aa1!aaaa",
        },
    )

    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh_response = client.post(
        "/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    second_refresh_response = client.post(
        "/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert first_refresh_response.status_code == 200
    assert second_refresh_response.status_code == 401
    assert second_refresh_response.json() == {"detail": "Invalid refresh token"}


# New refresh token should work too
def test_refresh_new_token_can_be_used_again():
    client.post(
        "/register",
        json={
            "login": "refresh_again_user",
            "password": "Aa1!aaaa",
            "email": "refresh_again_user@example.com",
        },
    )

    login_response = client.post(
        "/login",
        json={
            "login": "refresh_again_user",
            "password": "Aa1!aaaa",
        },
    )

    first_refresh_token = login_response.json()["refresh_token"]

    first_refresh_response = client.post(
        "/refresh",
        json={
            "refresh_token": first_refresh_token,
        },
    )

    second_refresh_token = first_refresh_response.json()["refresh_token"]

    second_refresh_response = client.post(
        "/refresh",
        json={
            "refresh_token": second_refresh_token,
        },
    )

    assert first_refresh_response.status_code == 200
    assert second_refresh_response.status_code == 200
    assert_refresh_response_json(second_refresh_response)


# Refresh token does not exist
def test_refresh_invalid_refresh_token():
    response = client.post(
        "/refresh",
        json={
            "refresh_token": "invalid_refresh_token",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


# Missing refresh token field
def test_refresh_without_refresh_token():
    response = client.post(
        "/refresh",
        json={},
    )

    assert response.status_code == 422