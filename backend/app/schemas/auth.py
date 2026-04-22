"""
Auth schemas — hardened
- RegisterRequest now requires student_id, department, academic_year
- student_id never appears in any response schema
- academic_year validated 1-4 at Pydantic layer (belt + suspenders with DB CHECK)
- JWT payload explicitly typed
"""
import re
from pydantic import BaseModel, EmailStr, field_validator, model_validator, Field
from typing import Optional


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    student_id: str = Field(..., min_length=3, max_length=50)
    department: str = Field(..., min_length=2, max_length=100)
    academic_year: int = Field(..., ge=1, le=4)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("student_id")
    @classmethod
    def student_id_format(cls, v: str) -> str:
        # Allow alphanumeric + dash/underscore (e.g. CS21B123, 25NU1A4430)
        if not re.match(r"^[A-Za-z0-9_\-]{3,50}$", v):
            raise ValueError("Student ID must be alphanumeric (dashes/underscores allowed)")
        return v.upper()  # normalize to uppercase

    @field_validator("department")
    @classmethod
    def department_clean(cls, v: str) -> str:
        return v.strip()


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Token ─────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    anon_id: str     # safe public identifier
    role: str
    institution_id: int


# ── User response — student_id EXCLUDED ───────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    anon_id: str
    email: str
    role: str
    department: str
    academic_year: int
    trust_score: float
    institution_id: int
    is_verified: bool

    # student_id deliberately omitted

    model_config = {"from_attributes": True}


class UserPublicResponse(BaseModel):
    """Minimal public profile — used where full UserResponse is too much"""
    anon_id: str
    department: str
    academic_year: int
    role: str
    trust_score: float

    model_config = {"from_attributes": True}


# ── JWT payload (internal use) ────────────────────────────────────────────────

class JWTPayload(BaseModel):
    sub: str           # user.id as string
    institution_id: int
    role: str
    type: str          # access | refresh
    exp: int
