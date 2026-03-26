from backend.tests.api_tests.test_base import client


def assert_login_response_json(response):
    data = response.json()

    assert response.status_code == 200
    assert "access_token" in data
    assert "refresh_token" in data
    assert "token_type" in data
    assert data["access_token"] != ""
    assert data["refresh_token"] != ""
    assert data["token_type"] == "bearer"
    assert data["access_token"] != data["refresh_token"]


# Basic successful login
def test_login_success():
    client.post(
        "/register",
        json={
            "login": "login_success_user",
            "password": "Aa1!aaaa",
            "email": "login_success_user@example.com",
        },
    )

    response = client.post(
        "/login",
        json={
            "login": "login_success_user",
            "password": "Aa1!aaaa",
        },
    )

    assert response.status_code == 200


# User does not exist
def test_login_user_not_found():
    response = client.post(
        "/login",
        json={
            "login": "missing_user",
            "password": "Aa1!aaaa",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid login or password"}


# Wrong password for existing user
def test_login_wrong_password():
    client.post(
        "/register",
        json={
            "login": "wrong_password_user",
            "password": "Aa1!aaaa",
            "email": "wrong_password_user@example.com",
        },
    )

    response = client.post(
        "/login",
        json={
            "login": "wrong_password_user",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid login or password"}


# Check full json in normal successful login
def test_login_returns_correct_json():
    client.post(
        "/register",
        json={
            "login": "json_user",
            "password": "Aa1!aaaa",
            "email": "json_user@example.com",
        },
    )

    response = client.post(
        "/login",
        json={
            "login": "json_user",
            "password": "Aa1!aaaa",
        },
    )

    assert_login_response_json(response)


# Check full json after repeated login
def test_login_twice_returns_correct_json():
    client.post(
        "/register",
        json={
            "login": "login_twice_user",
            "password": "Aa1!aaaa",
            "email": "login_twice_user@example.com",
        },
    )

    response_1 = client.post(
        "/login",
        json={
            "login": "login_twice_user",
            "password": "Aa1!aaaa",
        },
    )

    response_2 = client.post(
        "/login",
        json={
            "login": "login_twice_user",
            "password": "Aa1!aaaa",
        },
    )

    assert_login_response_json(response_1)
    assert_login_response_json(response_2)
    assert response_1.json()["refresh_token"] != response_2.json()["refresh_token"]


# Check full json for another user too
def test_login_another_user_returns_correct_json():
    client.post(
        "/register",
        json={
            "login": "another_login_user",
            "password": "Bb2@bbbb",
            "email": "another_login_user@example.com",
        },
    )

    response = client.post(
        "/login",
        json={
            "login": "another_login_user",
            "password": "Bb2@bbbb",
        },
    )

    assert_login_response_json(response)


# Two different users should both get correct json
def test_login_two_users_return_correct_json():
    client.post(
        "/register",
        json={
            "login": "first_json_user",
            "password": "Aa1!aaaa",
            "email": "first_json_user@example.com",
        },
    )

    client.post(
        "/register",
        json={
            "login": "second_json_user",
            "password": "Bb2@bbbb",
            "email": "second_json_user@example.com",
        },
    )

    response_1 = client.post(
        "/login",
        json={
            "login": "first_json_user",
            "password": "Aa1!aaaa",
        },
    )

    response_2 = client.post(
        "/login",
        json={
            "login": "second_json_user",
            "password": "Bb2@bbbb",
        },
    )

    assert_login_response_json(response_1)
    assert_login_response_json(response_2)
    assert response_1.json()["access_token"] != response_2.json()["access_token"]
    assert response_1.json()["refresh_token"] != response_2.json()["refresh_token"]


# Missing login field
def test_login_without_login():
    response = client.post(
        "/login",
        json={
            "password": "Aa1!aaaa",
        },
    )

    assert response.status_code == 422


# Missing password field
def test_login_without_password():
    response = client.post(
        "/login",
        json={
            "login": "some_user",
        },
    )

    assert response.status_code == 422