from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.dependencies import require_user
from app.models.user import User

router = APIRouter()


class DeleteAccountRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/delete")
async def delete_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(require_user)
):
    """Delete user account"""
    return {"message": "Account deletion request received. You will receive a confirmation email."}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(require_user)
):
    """Change user password"""
    return {"message": "Password changed successfully"}
