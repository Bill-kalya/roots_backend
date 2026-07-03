from pydantic import BaseModel, EmailStr, model_validator, ConfigDict

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.core.security import PasswordValidator
from app.models.user import UserRole

class UserBase(BaseModel):

    email: EmailStr
    full_name: str

    @model_validator(mode="before")
    @classmethod
    def normalize_email(cls, values):
        # Normalize email to lowercase and strip whitespace before validation
        if isinstance(values, dict):
            email = values.get("email")
            if isinstance(email, str):
                values["email"] = email.strip().lower()
        return values

class PasswordStrengthRequest(BaseModel):
    password: str

class PasswordCheckResponse(BaseModel):
    is_valid: bool
    failed_requirements: List[str] = []
    checks: dict = {}
    suggestion: str = "Use 8+ chars with Upper, lower, number, special char. Avoid common words."

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @model_validator(mode="before")
    @classmethod
    def normalize_email(cls, values):
        if isinstance(values, dict):
            email = values.get("email")
            if isinstance(email, str):
                values["email"] = email.strip().lower()
        return values

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class UserCreate(UserBase):
    password: str
    enable_mfa: bool = False
    interests: list[str] = []

    role: UserRole = UserRole.USER  # default to regular user



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
            # Build complete list of all requirements with status
            all_requirements = {
                'min_length': ('8+ characters', len(password) >= 8),
                'max_length': ('128 characters max', len(password) <= 128),
                'has_uppercase': ('1 uppercase letter (A-Z)', bool(__import__('re').search(r'[A-Z]', password))),
                'has_lowercase': ('1 lowercase letter (a-z)', bool(__import__('re').search(r'[a-z]', password))),
                'has_digit': ('1 number (0-9)', bool(__import__('re').search(r'\d', password))),
                'has_special': ('1 special char (!@#$%^&*(),.?":{}|<>)', bool(__import__('re').search(r'[!@#$%^&*(),.?":{}|<>]', password))),
                'no_common_patterns': ('No common patterns (password123, qwerty, 123456)', not any([
                    password.lower() in ["password", "admin", "123456", "qwerty", "letmein"],
                    __import__('re').search(r'(.)\1{3,}', password),
                    __import__('re').search(r'12345|54321|abcdef', password.lower())
                ]))
            }
            
            # Format complete requirements list
            req_list = []
            for key, (desc, met) in all_requirements.items():
                status = "✓" if met else "✗"
                req_list.append(f"{status} {desc}")
            
            error_msg = "Password must meet all requirements:\n" + "\n".join(req_list)
            error_msg += "\n\nExample: TestPass123!Abc"
            raise ValueError(error_msg)
        return data

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @model_validator(mode="before")
    @classmethod
    def normalize_email(cls, values):
        if isinstance(values, dict):
            email = values.get("email")
            if isinstance(email, str):
                values["email"] = email.strip().lower()
        return values


class MFALoginStep2Request(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str
    challenge_id: str

    @model_validator(mode="before")
    @classmethod
    def normalize_email(cls, values):
        if isinstance(values, dict):
            email = values.get("email")
            if isinstance(email, str):
                values["email"] = email.strip().lower()
        return values


class MFALoginStep1Response(BaseModel):
    requires_mfa: bool
    challenge_id: Optional[str] = None
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
    role: UserRole
    merchant_approved: bool
    created_at: datetime



class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int | None = None



class TokenRefresh(BaseModel):
    refresh_token: str


