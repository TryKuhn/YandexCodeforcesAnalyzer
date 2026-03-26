from backend.tests.api_tests.test_base import client

# Basic successful case
def test_register_success():
    response = client.post(
        "/register",
        json={
            "login": "test_user_success",
            "password": "Aa1!aaaa",
            "email": "test_user_success@example.com",
        },
    )
    assert response.status_code == 200


# Same user tries to register again
def test_register_existing_user():
    response = client.post(
        "/register",
        json={
            "login": "test_user_duplicate",
            "password": "Aa1!aaaa",
            "email": "test_user_duplicate@example.com",
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/register",
        json={
            "login": "test_user_duplicate",
            "password": "Bb2@bbbb",
            "email": "test_user_duplicate_second@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "User with this login already exists"}


# Password is shorter than 8 symbols
def test_register_password_too_short():
    response = client.post(
        "/register",
        json={
            "login": "short_password_user",
            "password": "Aa1!aaa",
            "email": "short_password_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must be at least 8 characters long"}


# Password has exactly 8 symbols
def test_register_password_exactly_8_symbols():
    response = client.post(
        "/register",
        json={
            "login": "exactly_8_user",
            "password": "Aa1!aaaa",
            "email": "exactly_8_user@example.com",
        },
    )
    assert response.status_code == 200


# No digit in password
def test_register_password_without_digit():
    response = client.post(
        "/register",
        json={
            "login": "without_digit_user",
            "password": "Aa!aaaaa",
            "email": "without_digit_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain at least one digit"}


# No lowercase latin letter
def test_register_password_without_lowercase_latin_letter():
    response = client.post(
        "/register",
        json={
            "login": "without_lowercase_user",
            "password": "AA1!AAAA",
            "email": "without_lowercase_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain at least one lowercase Latin letter"}


# No uppercase latin letter
def test_register_password_without_uppercase_latin_letter():
    response = client.post(
        "/register",
        json={
            "login": "without_uppercase_user",
            "password": "aa1!aaaa",
            "email": "without_uppercase_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain at least one uppercase Latin letter"}


# No special symbol
def test_register_password_without_special_symbol():
    response = client.post(
        "/register",
        json={
            "login": "without_special_user",
            "password": "Aa1aaaaa",
            "email": "without_special_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain at least one special symbol"}


# Password has only digits
def test_register_password_only_digits():
    response = client.post(
        "/register",
        json={
            "login": "only_digits_user",
            "password": "12345678",
            "email": "only_digits_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password format is invalid"}


# Password has only special symbols
def test_register_password_only_special_symbols():
    response = client.post(
        "/register",
        json={
            "login": "only_specials_user",
            "password": "!@#$%^&*",
            "email": "only_specials_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password format is invalid"}


# Password has only lowercase latin letters
def test_register_password_only_lowercase_latin_letters():
    response = client.post(
        "/register",
        json={
            "login": "only_lowercase_user",
            "password": "aaabbbccc",
            "email": "only_lowercase_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Only lowercase letters!"}


# Password has only uppercase latin letters
def test_register_password_only_uppercase_latin_letters():
    response = client.post(
        "/register",
        json={
            "login": "only_uppercase_user",
            "password": "AAABBBCCC",
            "email": "only_uppercase_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Only uppercase letters!"}


# Password has cyrillic letters
def test_register_password_with_cyrillic_letters():
    response = client.post(
        "/register",
        json={
            "login": "cyrillic_password_user",
            "password": "Пароль1!",
            "email": "cyrillic_password_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain only Latin letters"}


# Password has both latin and cyrillic letters
def test_register_password_with_mixed_latin_and_cyrillic_letters():
    response = client.post(
        "/register",
        json={
            "login": "mixed_letters_user",
            "password": "Aa1!тест",
            "email": "mixed_letters_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must contain only Latin letters"}


# Password has a space
def test_register_password_with_space():
    response = client.post(
        "/register",
        json={
            "login": "password_with_space_user",
            "password": "Aa1! aaab",
            "email": "password_with_space_user@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Password must not contain spaces"}


# Long valid password
def test_register_long_valid_password():
    response = client.post(
        "/register",
        json={
            "login": "long_valid_password_user",
            "password": "VeryStrongPassword123!A",
            "email": "long_valid_password_user@example.com",
        },
    )
    assert response.status_code == 200


# Minimal valid password by rules
def test_register_password_minimal_valid_complexity():
    response = client.post(
        "/register",
        json={
            "login": "minimal_valid_complexity_user",
            "password": "A1!bobau",
            "email": "minimal_valid_complexity_user@example.com",
        },
    )
    assert response.status_code == 200


# Email is not valid
def test_register_with_invalid_email():
    response = client.post(
        "/register",
        json={
            "login": "invalid_email_user",
            "password": "Aa1!aaaa",
            "email": "not-an-email",
        },
    )
    assert response.status_code == 422