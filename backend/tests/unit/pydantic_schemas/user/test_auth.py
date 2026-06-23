"""Unit tests for api/pydantic_schemas/user/auth.py — validation rules."""
import pytest
from pydantic import ValidationError

from api.pydantic_schemas.user.auth import (ChangePassword, UserLogin,
                                            UserRegister)
from api.pydantic_schemas.user.auth import _validate_password_rules

VALID_PWD = "Aa1!aaaa"


def test_valid_password_passes():
    assert _validate_password_rules(VALID_PWD) == VALID_PWD


@pytest.mark.parametrize(
    "pwd, fragment",
    [
        ("Aa1! aaa", "spaces"),
        ("Ab1!ффф", "Latin"),
        ("Aa1!aa", "at least 8"),
        ("Aa1!" + "a" * 30, "exceed"),
        ("AA1!AAAA", "lowercase"),
        ("aa1!aaaa", "uppercase"),
        ("Aa!aaaaa", "digit"),
        ("Aa1aaaaa", "special"),
    ],
)
def test_invalid_passwords_rejected(pwd, fragment):
    with pytest.raises(ValueError) as exc:
        _validate_password_rules(pwd)
    assert fragment in str(exc.value)


def test_user_register_valid():
    u = UserRegister(login="valid_user", password=VALID_PWD, email="a@b.com")
    assert u.login == "valid_user"


@pytest.mark.parametrize(
    "login",
    ["abc", "a" * 31, "bad login!", "with space"],
)
def test_user_register_invalid_login(login):
    with pytest.raises(ValidationError):
        UserRegister(login=login, password=VALID_PWD, email="a@b.com")


def test_user_register_invalid_password():
    with pytest.raises(ValidationError):
        UserRegister(login="valid_user", password="weak", email="a@b.com")


def test_user_login_accepts_any_strings():
    m = UserLogin(login="x", password="y")
    assert m.login == "x" and m.password == "y"


def test_change_password_validates_new_password():
    m = ChangePassword(
        old_password="whatever",
        new_password=VALID_PWD,
        confirm_password=VALID_PWD,
    )
    assert m.new_password == VALID_PWD

    with pytest.raises(ValidationError):
        ChangePassword(
            old_password="whatever",
            new_password="weak",
            confirm_password="weak",
        )
