from pydantic import BaseModel, EmailStr, model_validator, ConfigDict

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.core.security import PasswordValidator

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class PasswordStrengthRequest(BaseModel):
    password: str

class PasswordCheckResponse(BaseModel):
    is_valid: bool
    failed_requirements: List[str] = []
    checks: dict = {}
    suggestion: str = "Use 8+ chars with Upper, lower, number, special char. Avoid common words."

class UserCreate(UserBase):
    password: str
    enable_mfa: bool = False
    interests: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def validate_password(cls, data):
        if not isinstance(data, dict):
            return data
        
        password = data.get("password")
        if not password:
            return data
        
        from app.core.security import PasswordValidator
        is_valid, checks = PasswordValidator.validate(password)
        if not is_valid:
            failed = [k for k, v in checks.items() if not v]
            messages = {
                'min_length': 'at least 8 characters',
                'max_length': 'maximum 128 characters',
                'has_uppercase': 'one uppercase letter (A-Z)',
                'has_lowercase': 'one lowercase letter (a-z)',
                'has_digit': 'one number (0-9)',
                'has_special': 'one special char (!@#$%^&*(),.?":{}|<> )',
                'no_common_patterns': 'no common/repeated patterns (password123, qwerty, 123456)'
            }
            failed_msgs = [messages.get(k, k.replace('_', ' ').title()) for k in failed]
            raise ValueError(f"Password invalid: {', '.join(failed_msgs)}. Suggestion: TestPass123!Abc")
        return data

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class MFALoginStep2Request(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str


class MFALoginStep1Response(BaseModel):
    requires_mfa: bool
    user_id: Optional[UUID] = None


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code: str


class MFAEnableEnrollRequest(BaseModel):
    code: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    is_admin: bool
    created_at: datetime



class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


