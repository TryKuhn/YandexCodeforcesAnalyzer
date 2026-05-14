from tests.api_tests.test_base import client

BASE = "/api/auth"


def _register(login, password="Aa1!aaaa", email=None):
    return client.post(
        f"{BASE}/register",
        json={
            "login": login,
            "password": password,
            "email": email or f"{login}@example.com",
        },
    )


def test_register_success():
    assert _register("test_user_success").status_code == 200


def test_register_existing_user():
    _register("test_user_duplicate")
    response = _register("test_user_duplicate", password="Bb2@bbbb", email="test_user_duplicate_second@example.com")
    assert response.status_code == 400
    assert response.json() == {"detail": "User with this login already exists"}


def test_register_password_too_short():
    r = _register("short_password_user", password="Aa1!aaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must be at least 8 characters long"}


def test_register_password_exactly_8_symbols():
    assert _register("exactly_8_user").status_code == 200


def test_register_password_without_digit():
    r = _register("without_digit_user", password="Aa!aaaaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one digit"}


def test_register_password_without_lowercase_latin_letter():
    r = _register("without_lowercase_user", password="AA1!AAAA")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one lowercase Latin letter"}


def test_register_password_without_uppercase_latin_letter():
    r = _register("without_uppercase_user", password="aa1!aaaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one uppercase Latin letter"}


def test_register_password_without_special_symbol():
    r = _register("without_special_user", password="Aa1aaaaa")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain at least one special symbol"}


def test_register_password_only_digits():
    r = _register("only_digits_user", password="12345678")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password format is invalid"}


def test_register_password_only_special_symbols():
    r = _register("only_specials_user", password="!@#$%^&*")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password format is invalid"}


def test_register_password_only_lowercase_latin_letters():
    r = _register("only_lowercase_user", password="aaabbbccc")
    assert r.status_code == 400
    assert r.json() == {"detail": "Only lowercase letters!"}


def test_register_password_only_uppercase_latin_letters():
    r = _register("only_uppercase_user", password="AAABBBCCC")
    assert r.status_code == 400
    assert r.json() == {"detail": "Only uppercase letters!"}


def test_register_password_with_cyrillic_letters():
    r = _register("cyrillic_password_user", password="Пароль1!")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain only Latin letters"}


def test_register_password_with_mixed_latin_and_cyrillic_letters():
    r = _register("mixed_letters_user", password="Aa1!тест")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must contain only Latin letters"}


def test_register_password_with_space():
    r = _register("password_with_space_user", password="Aa1! aaab")
    assert r.status_code == 400
    assert r.json() == {"detail": "Password must not contain spaces"}


def test_register_long_valid_password():
    assert _register("long_valid_password_user", password="VeryStrongPassword123!A").status_code == 200


def test_register_password_minimal_valid_complexity():
    assert _register("minimal_valid_complexity_user", password="A1!bobau").status_code == 200


def test_register_with_invalid_email():
    r = _register("invalid_email_user", email="not-an-email")
    assert r.status_code == 400
