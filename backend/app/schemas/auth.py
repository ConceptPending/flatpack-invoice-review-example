from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class LoginResponse(BaseModel):
    message: str = "Login successful"
