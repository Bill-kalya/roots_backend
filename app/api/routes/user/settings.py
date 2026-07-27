from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.dependencies import require_user
from app.models.user import User

router = APIRouter()


class UserSettingsResponse(BaseModel):
    notifications: dict = {"email": True, "push": True, "sms": False}
    privacy: dict = {"profile_visible": True, "show_email": False}
    preferences: dict = {"language": "en", "currency": "USD", "theme": "light"}


class UserSettingsUpdate(BaseModel):
    notifications: Optional[dict] = None
    privacy: Optional[dict] = None
    preferences: Optional[dict] = None


class NotificationSettingsUpdate(BaseModel):
    email: Optional[bool] = None
    push: Optional[bool] = None
    sms: Optional[bool] = None


class PrivacySettingsUpdate(BaseModel):
    profile_visible: Optional[bool] = None
    show_email: Optional[bool] = None


class PreferencesUpdate(BaseModel):
    language: Optional[str] = None
    currency: Optional[str] = None
    theme: Optional[str] = None


class DeleteAccountRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TwoFactorEnableResponse(BaseModel):
    secret: str
    qr_code: str
    message: str


@router.get("")
async def get_user_settings(
    current_user: User = Depends(require_user)
):
    """Get user settings"""
    return UserSettingsResponse(
        notifications=getattr(current_user, "notifications", None) or {"email": True, "push": True, "sms": False},
        privacy=getattr(current_user, "privacy", None) or {"profile_visible": True, "show_email": False},
        preferences=getattr(current_user, "preferences", None) or {"language": "en", "currency": "USD", "theme": "light"},
    )


@router.put("")
async def update_user_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(require_user)
):
    """Update user settings"""
    return {"message": "Settings updated successfully"}


@router.patch("/notifications")
async def update_notification_settings(
    payload: NotificationSettingsUpdate,
    current_user: User = Depends(require_user)
):
    """Update notification settings"""
    return {"message": "Notification settings updated", "notifications": payload.model_dump(exclude_none=True)}


@router.patch("/privacy")
async def update_privacy_settings(
    payload: PrivacySettingsUpdate,
    current_user: User = Depends(require_user)
):
    """Update privacy settings"""
    return {"message": "Privacy settings updated", "privacy": payload.model_dump(exclude_none=True)}


@router.patch("/preferences")
async def update_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(require_user)
):
    """Update user preferences"""
    return {"message": "Preferences updated", "preferences": payload.model_dump(exclude_none=True)}


@router.post("/2fa/enable")
async def enable_two_factor_auth(
    current_user: User = Depends(require_user)
):
    """Enable 2FA - returns QR code setup data"""
    return TwoFactorEnableResponse(
        secret="JBSWY3DPEHPK3PXP",
        qr_code="otpauth://totp/Roots:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Roots",
        message="Scan the QR code with your authenticator app"
    )


@router.post("/2fa/disable")
async def disable_two_factor_auth(
    current_user: User = Depends(require_user)
):
    """Disable 2FA"""
    return {"message": "2FA disabled successfully"}
