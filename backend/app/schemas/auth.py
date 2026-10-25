"""Pydantic schemas for auth endpoints."""
from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("business_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("business_name must not be blank")
        return v.strip()


class RegisterResponse(BaseModel):
    id: str
    business_name: str


class LoginRequest(BaseModel):
    business_name: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
