from pydantic import BaseModel, EmailStr, field_validator
import re

class UserRegister(BaseModel):
    login: str
    password: str
    email: EmailStr

    @field_validator('login')
    def validate_login(self, value: str):
        if len(value) < 5:
            raise ValueError('Login length must contain at least 5 character')
        if len(value) > 30:
            raise ValueError('Login length must contain at most 30 characters')

        value_without_underscore = value.replace('_', '')
        if not value_without_underscore.isalnum():
            raise ValueError('Login must contain only alphanumeric characters')

        return value

    @field_validator('password')
    def validate_password(self, value: str):
        if len(value) < 8:
            raise ValueError('Password length must contain at least 8 characters')
        if len(value) > 30:
            raise ValueError('Password length must contain at most 30 characters')
        if not re.search('[a-z]', value):
            raise ValueError('Password must contain lowercase letters')
        if not re.search('[A-Z]', value):
            raise ValueError('Password must contain uppercase letters')
        if not re.search('[0-9]', value):
            raise ValueError('Password must contain numbers')
        if not re.search('\.,<>_\?!@#\$%\^&\*\(\)', value):
            raise ValueError('Password must contain special characters')

        return value


class UserLogin(BaseModel):
    login: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
