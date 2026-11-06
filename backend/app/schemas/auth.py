import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _check_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(v.encode()) > 72:
        raise ValueError("Password is too long (max 72 bytes)")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain at least one letter and one number")
    return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return _check_password(v)

    @field_validator("confirm_password")
    @classmethod
    def _match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v):
        return _check_password(v)


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v):
        return _check_password(v)


class ProjectIn(BaseModel):
    project_name: str = Field(min_length=2, max_length=200)
    environment: str = "development"

    @field_validator("environment")
    @classmethod
    def _env(cls, v):
        v = v.lower()
        if v not in ("development", "testing", "staging"):
            raise ValueError("Environment must be development, testing or staging")
        return v


class OnboardingIn(ProjectIn):
    organization_name: str = Field(min_length=2, max_length=200)
