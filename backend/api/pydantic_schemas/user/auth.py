import re

from pydantic import BaseModel, EmailStr, field_validator


def _validate_password_rules(value: str) -> str:
    if " " in value:
        raise ValueError("Password must not contain spaces")

    if any(c.isalpha() and not c.isascii() for c in value):
        raise ValueError("Password must contain only Latin letters")

    has_lower = bool(re.search("[a-z]", value))
    has_upper = bool(re.search("[A-Z]", value))
    has_digit = bool(re.search("[0-9]", value))
    has_special = bool(re.search(r"[.,<>_?!@#$%^&*()]", value))

    if has_lower and not has_upper and not has_digit and not has_special:
        raise ValueError("Only lowercase letters!")
    if has_upper and not has_lower and not has_digit and not has_special:
        raise ValueError("Only uppercase letters!")
    if not has_lower and not has_upper and not has_special:
        raise ValueError("Password format is invalid")
    if not has_lower and not has_upper and not has_digit:
        raise ValueError("Password format is invalid")

    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(value) > 30:
        raise ValueError("Password length must not exceed 30 characters")
    if not has_lower:
        raise ValueError("Password must contain at least one lowercase Latin letter")
    if not has_upper:
        raise ValueError("Password must contain at least one uppercase Latin letter")
    if not has_digit:
        raise ValueError("Password must contain at least one digit")
    if not has_special:
        raise ValueError("Password must contain at least one special symbol")

    return value


class UserRegister(BaseModel):
    login: str
    password: str
    email: EmailStr

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: str):
        if len(value) < 5:
            raise ValueError("Login length must contain at least 5 characters")
        if len(value) > 30:
            raise ValueError("Login length must contain at most 30 characters")

        value_without_underscore = value.replace("_", "")
        if not value_without_underscore.isalnum():
            raise ValueError("Login must contain only alphanumeric characters")

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str):
        return _validate_password_rules(value)


class UserLogin(BaseModel):
    login: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class Authorization(BaseModel):
    Bearer: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str):
        return _validate_password_rules(value)
