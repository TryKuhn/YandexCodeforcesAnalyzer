"""Auth request/response schemas and shared password validation."""
import re

from pydantic import BaseModel, EmailStr, field_validator


def _validate_password_rules(value: str) -> str:
    """Enforce password policy and return the value, raising on violations.

    Requires 8-30 ASCII-only characters with no spaces and at least one
    lowercase letter, uppercase letter, digit, and special symbol.
    """
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
    """Registration payload: login, password, and email."""

    login: str
    password: str
    email: EmailStr

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: str):
        """Require a 5-30 character alphanumeric (plus underscore) login."""
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
        """Apply the shared password policy to the registration password."""
        return _validate_password_rules(value)


class UserLogin(BaseModel):
    """Login payload: login and password."""

    login: str
    password: str


class Token(BaseModel):
    """Issued auth token pair and its type."""

    access_token: str
    refresh_token: str
    token_type: str


class RefreshRequest(BaseModel):
    """Request carrying a refresh token to rotate."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request carrying the refresh token identifying the session(s) to revoke."""

    refresh_token: str


class Authorization(BaseModel):
    """Bearer authorization header value wrapper."""

    Bearer: str


class ChangePassword(BaseModel):
    """Change-password payload: old password plus new/confirmation."""

    old_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str):
        """Apply the shared password policy to the new password."""
        return _validate_password_rules(value)
