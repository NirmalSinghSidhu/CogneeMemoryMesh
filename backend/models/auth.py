from pydantic import BaseModel, EmailStr, Field


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    workspace_name: str | None = Field(default=None, max_length=200)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    tenant: TenantResponse


class MeResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
