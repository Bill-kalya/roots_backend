from fastapi import APIRouter, Depends, HTTPException, status, Request

from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from app.db.session import get_db
from app.schemas.user import (
    UserCreate,
    UserLogin,
    MFALoginStep1Response,
    MFALoginStep2Request,
    Token,
    TokenRefresh,
    UserResponse,
    PasswordStrengthRequest,
    PasswordCheckResponse,
    MFASetupResponse,
    MFAEnableEnrollRequest,
)

from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, get_redis
from app.core.config import settings
from sqlalchemy import select
from app.models.user import User
from datetime import datetime


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Begin MFA enrollment: generate secret and QR."""
    service = AuthService(db, redis)
    return await service.enable_mfa(current_user.id)


@router.post("/mfa/verify-enroll")
async def mfa_verify_enroll(
    payload: MFAEnableEnrollRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Verify MFA code and enable MFA for the current user."""

    service = AuthService(db, redis)
    if payload is None:
        raise HTTPException(status_code=422, detail="Missing payload")

    ok = await service.verify_mfa_and_enable(current_user.id, payload.code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    return {"success": True, "enabled": True}





@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Register new user (sends verification email)."""
    service = AuthService(db, redis)
    try:
        user = await service.register_user(user_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    return user


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """Verify email address using token.

    Returns JSON only (no redirects) to avoid cross-origin redirect/CORS issues.
    Frontend is responsible for navigation after calling this endpoint.
    """
    query = select(User).where(User.verification_token == token)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_OR_EXPIRED_TOKEN",
                "message": "Verification link is invalid or has expired. Please request a new one.",
            },
        )

    if user.verification_token_expires and user.verification_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_OR_EXPIRED_TOKEN",
                "message": "Verification link is invalid or has expired. Please request a new one.",
            },
        )

    # Idempotent: if already verified, still return success.
    if not user.is_verified:
        user.is_active = True
        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        await db.commit()

    return {
        "success": True,
        "verified": True,
        "message": "Email verified successfully.",
    }




@router.post("/resend-verification")
async def resend_verification(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Regenerate and re-send email verification."""
    email = payload.get("email") if isinstance(payload, dict) else None
    if not email:
        raise HTTPException(status_code=422, detail="Missing email")

    service = AuthService(db, redis)
    try:
        sent = await service.resend_verification_email(user_email=email, request=None)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

    if sent:
        return {"message": "Verification email re-sent"}

    raise HTTPException(status_code=400, detail="Email already verified")


@router.post("/login")

async def login(
    request: Request,
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Login user (2-step MFA if enabled)."""
    service = AuthService(db, redis)

    # authenticate_user returns either:
    # - {"requires_mfa": True, "user_id": "..."}
    # - {"user": ..., "tokens": ..., "session_id": ..., "role": ..., "requires_mfa": False}
    try:
        result = await service.authenticate_user(
            credentials.email,
            credentials.password,
            request=request,
            mfa_code=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if result.get("requires_mfa"):
        # Step 1 response: no JWT issued yet.
        return MFALoginStep1Response(**result)

    return result.get("tokens")


@router.post("/login/verify-mfa")
async def verify_mfa_login(
    request: Request,
    credentials: MFALoginStep2Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Login step 2: verify MFA code and return JWT tokens."""
    service = AuthService(db, redis)

    try:
        result = await service.authenticate_user(
            credentials.email,
            credentials.password,
            request=request,
            mfa_code=credentials.mfa_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email/password or MFA")

    if result.get("requires_mfa"):
        # Should not happen if client sent mfa_code, but keep safe.
        raise HTTPException(status_code=400, detail="MFA code required")

    return result.get("tokens")



@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Refresh access token."""
    service = AuthService(db, redis)
    tokens = await service.refresh_tokens(refresh_data.refresh_token, request=None, current_session_id="")

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return tokens


@router.post("/logout")
async def logout(
    request: Request,
    current_user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Logout user by revoking the provided access token (JWT blacklist)."""

    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    token = auth_header.split(" ", 1)[1].strip()

    # Token blacklist is handled by TokenBlacklist (Redis). We blacklist only the access token.
    from app.core.security import TokenBlacklist
    blacklist = TokenBlacklist(redis)
    # Access token expiry is short-lived; blacklist TTL can be set conservatively to access lifetime.
    # If your system rotates/extends tokens, consider persisting exp claim and using it here.
    await blacklist.blacklist_token(token, expires_in=60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    return {"success": True, "message": "Logged out successfully"}



@router.post("/validate-password", response_model=PasswordCheckResponse)
async def validate_password_strength(
    password_data: PasswordStrengthRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """API for frontend password strength validation"""
    service = AuthService(db, redis)
    result = await service.validate_password(password_data.password)
    return PasswordCheckResponse(**result)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    """Get current user info"""
    return current_user
